from flask import Flask, request, jsonify
from flask_cors import CORS
from chromadb import PersistentClient
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import pika
import redis
import json
import uuid
import hashlib
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Redis client
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    redis_client.ping()  # Test connection
    logger.info("Redis connection successful")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

# Initialize PersistentClient and load the collection
try:
    client = PersistentClient(
        path="./chroma_data",  # Adjust this path as needed
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection("pdf_knowledge_base")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    logger.info("ChromaDB and SentenceTransformer initialized successfully")
except Exception as e:
    logger.error(f"ChromaDB initialization failed: {e}")
    collection = None
    model = None

# Function to create a Redis cache key based on the query
def get_cache_key(query, user_id):
    return hashlib.sha256(f"{user_id}:{query}".encode()).hexdigest()

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Django to verify RAG service availability"""
    status = {
        "status": "healthy",
        "service": "RAG API",
        "redis": redis_client is not None,
        "chromadb": collection is not None,
        "model": model is not None
    }
    
    # Test RabbitMQ connection
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        connection.close()
        status["rabbitmq"] = True
    except:
        status["rabbitmq"] = False
    
    return jsonify(status), 200

@app.route("/submit_query", methods=["POST"])
def submit_query():
    try:
        user_query = request.json.get("query")
        user_id = request.json.get("user_id", "default_user")
        correlation_id = str(uuid.uuid4())

        logger.info(f"Received query from user {user_id}: {user_query[:100]}...")

        # Check if the query result is already cached in Redis
        if redis_client:
            cache_key = get_cache_key(user_query, user_id)
            cached_response = redis_client.get(cache_key)

            if cached_response:
                logger.info("Found cached response")
                return jsonify(json.loads(cached_response))

        # Set up a new RabbitMQ connection and channel for each request
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    'localhost',
                    connection_attempts=3,
                    retry_delay=1
                )
            )
            channel = connection.channel()

            # Declare the queues to ensure they exist
            channel.queue_declare(queue='query_queue')
            channel.queue_declare(queue='response_queue')

            logger.info("RabbitMQ connection established")

            # Publish the query to RabbitMQ with user_id
            channel.basic_publish(
                exchange='',
                routing_key='query_queue',
                properties=pika.BasicProperties(
                    reply_to='response_queue',
                    correlation_id=correlation_id
                ),
                body=json.dumps({"query": user_query, "user_id": user_id})
            )

            logger.info(f"Query published to RabbitMQ with correlation_id: {correlation_id}")

            # Wait for response from the response queue with shorter timeout
            response_received = False
            for method_frame, properties, body in channel.consume('response_queue', inactivity_timeout=15):
                if method_frame is None:
                    logger.warning("Timeout waiting for response from worker")
                    break  # Timeout reached with no message
                if properties and properties.correlation_id == correlation_id:
                    channel.basic_ack(method_frame.delivery_tag)
                    response_data = json.loads(body)

                    # Cache the response in Redis with a TTL (e.g., 1 hour)
                    if redis_client:
                        redis_client.setex(cache_key, 3600, json.dumps(response_data))
                    
                    logger.info("Response received and cached")
                    response_received = True
                    
                    if connection.is_open:
                        connection.close()
                    return jsonify(response_data)

            if not response_received:
                if connection.is_open:
                    connection.close()
                logger.error("No response received from worker within timeout")
                return jsonify({
                    "response": "Le système met plus de temps que prévu à répondre. Veuillez réessayer.",
                    "context": []
                }), 504

        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"RabbitMQ connection error: {e}")
            return jsonify({
                "response": "Service de chat temporairement indisponible. Veuillez réessayer dans quelques instants.",
                "context": []
            }), 503

        except Exception as e:
            logger.error(f"Error while consuming from RabbitMQ: {e}")
            return jsonify({
                "response": "Une erreur s'est produite lors du traitement. Veuillez réessayer.",
                "context": []
            }), 500

    except Exception as e:
        logger.error(f"General error in submit_query: {e}")
        return jsonify({
            "response": "Une erreur inattendue s'est produite. Veuillez réessayer.",
            "context": []
        }), 500


if __name__ == "__main__":
    logger.info("Starting Flask RAG API server...")
    app.run(host="0.0.0.0", port=5001, debug=True)