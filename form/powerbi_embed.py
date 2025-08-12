import requests
import json
import logging
from django.conf import settings
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PowerBIEmbedService:
    """Service to handle Power BI embedding authentication and token management"""
    
    def __init__(self):
        # Power BI configuration - Add these to your settings.py
        self.client_id = getattr(settings, 'POWERBI_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'POWERBI_CLIENT_SECRET', '')
        self.tenant_id = getattr(settings, 'POWERBI_TENANT_ID', '')
        self.workspace_id = getattr(settings, 'POWERBI_WORKSPACE_ID', '')
        self.report_id = getattr(settings, 'POWERBI_REPORT_ID', '')
        
        # Azure AD endpoints
        self.authority_url = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = "https://analysis.windows.net/powerbi/api/.default"
        self.powerbi_api_url = "https://api.powerbi.com/v1.0/myorg"
    
    def get_access_token(self):
        """Get access token from Azure AD"""
        try:
            token_url = f"{self.authority_url}/oauth2/v2.0/token"
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': self.scope
            }
            
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data.get('access_token')
            
        except Exception as e:
            logger.error(f"Error getting Power BI access token: {e}")
            return None
    
    def get_embed_token(self, access_token):
        """Get embed token for the report"""
        try:
            embed_url = f"{self.powerbi_api_url}/groups/{self.workspace_id}/reports/{self.report_id}/GenerateToken"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Request body for embed token
            data = {
                "accessLevel": "View",
                "allowSaveAs": False
            }
            
            response = requests.post(embed_url, headers=headers, json=data)
            response.raise_for_status()
            
            embed_data = response.json()
            return embed_data.get('token')
            
        except Exception as e:
            logger.error(f"Error getting Power BI embed token: {e}")
            return None
    
    def get_report_info(self, access_token):
        """Get report information"""
        try:
            report_url = f"{self.powerbi_api_url}/groups/{self.workspace_id}/reports/{self.report_id}"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(report_url, headers=headers)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting Power BI report info: {e}")
            return None
    
    def get_embed_config(self):
        """Get complete embed configuration"""
        try:
            # Get access token
            access_token = self.get_access_token()
            if not access_token:
                return None
            
            # Get embed token
            embed_token = self.get_embed_token(access_token)
            if not embed_token:
                return None
            
            # Get report info
            report_info = self.get_report_info(access_token)
            if not report_info:
                return None
            
            # Return embed configuration
            embed_config = {
                'type': 'report',
                'id': self.report_id,
                'embedUrl': report_info.get('embedUrl'),
                'accessToken': embed_token,
                'tokenType': 1,  # Embed token
                'settings': {
                    'panes': {
                        'filters': {
                            'expanded': False,
                            'visible': True
                        },
                        'pageNavigation': {
                            'visible': True
                        }
                    },
                    'background': 1,  # Transparent
                    'layoutType': 0,  # Master
                    'contrastMode': 0,  # None
                    'bars': {
                        'statusBar': {
                            'visible': True
                        }
                    }
                }
            }
            
            return embed_config
            
        except Exception as e:
            logger.error(f"Error getting Power BI embed config: {e}")
            return None

# Global instance
powerbi_service = PowerBIEmbedService()