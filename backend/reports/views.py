"""
Reports API Views - REST endpoints for smart money analytics and reports.
"""
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request

from reports.generators.SmartMoneyConcentrationGenerator import SmartMoneyConcentrationGenerator
from reports.pojos.smartmoneyconcentration.SmartMoneyConcentrationRequest import SmartMoneyConcentrationRequest
from reports.Constants import LOG_PREFIX_SMART_MONEY_CONCENTRATION as LOG_PREFIX

logger = logging.getLogger(__name__)


# ==================== Response Helpers ====================

def buildErrorResponse(message: str, httpStatus: int) -> Response:
    """Build standardized error response."""
    return Response({'success': False, 'errorMessage': message}, status=httpStatus)


def buildSuccessResponse(data: dict) -> Response:
    """Build standardized success response."""
    return Response(data, status=status.HTTP_200_OK)


# ==================== Request Helpers ====================

def parseAndValidateRequest(requestData: dict) -> tuple[SmartMoneyConcentrationRequest, str]:
    """
    Parse and validate request data.
    
    Returns:
        Tuple of (request, errorMessage). errorMessage is None if valid.
    """
    reportRequest = SmartMoneyConcentrationRequest.fromDict(requestData or {})
    isValid, errorMessage = reportRequest.validate()
    return reportRequest, errorMessage if not isValid else None


def logRequest(reportRequest: SmartMoneyConcentrationRequest) -> None:
    """Log incoming API request."""
    logger.info("%s :: Request | Period: %d | MinPnL: %.0f | MinInvest: %.0f | Category: %s",
               LOG_PREFIX, reportRequest.pnlPeriod, float(reportRequest.minWalletPnl),
               float(reportRequest.minInvestmentAmount), reportRequest.category or "All")


def logResponse(reportResponse) -> None:
    """Log API response."""
    logger.info("%s :: Response | Markets: %d | Time: %.3fs",
               LOG_PREFIX, reportResponse.totalMarketsFound, reportResponse.executionTimeSeconds)


# ==================== API Endpoint ====================

@api_view(['POST'])
def getSmartMoneyConcentration(request: Request) -> Response:
    """
    Get smart money concentration report showing markets with highest 
    investment from qualifying smart wallets.
    
    Endpoint: POST /api/reports/smart-money/concentration
    
    Request Body:
        {
            "pnlPeriod": 30,              // Period in days (30, 60, 90)
            "minWalletPnl": 10000,        // Minimum PnL for qualifying wallets
            "minInvestmentAmount": 1000,  // Minimum investment per wallet in market
            "category": "Politics",       // Optional: Filter by wallet category
            "limit": 100,                 // Pagination limit (1-1000)
            "offset": 0                   // Pagination offset
        }
    
    Note: Only open positions with future end dates are included.
    """
    try:
        reportRequest, validationError = parseAndValidateRequest(request.data)
        
        if validationError:
            logger.info("%s :: Invalid request: %s", LOG_PREFIX, validationError)
            return buildErrorResponse(validationError, status.HTTP_400_BAD_REQUEST)
        
        logRequest(reportRequest)
        
        reportResponse = SmartMoneyConcentrationGenerator.generate(reportRequest)
        
        if not reportResponse.success:
            logger.info("%s :: Generation failed: %s", LOG_PREFIX, reportResponse.errorMessage)
            return buildErrorResponse(reportResponse.errorMessage, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logResponse(reportResponse)
        return buildSuccessResponse(reportResponse.toDict())
        
    except ValueError as e:
        logger.info("%s :: Invalid parameter: %s", LOG_PREFIX, str(e))
        return buildErrorResponse(f"Invalid parameter: {str(e)}", status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error("%s :: Unexpected error: %s", LOG_PREFIX, str(e), exc_info=True)
        return buildErrorResponse(f"Internal server error: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
