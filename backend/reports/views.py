"""
Reports API Views - REST endpoints for smart money analytics and reports.
"""
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request

from reports.generators.SmartMoneyConcentrationGenerator import SmartMoneyConcentrationGenerator
from reports.generators.MarketLevelsGenerator import MarketLevelsGenerator
from reports.pojos.smartmoneyconcentration.SmartMoneyConcentrationRequest import SmartMoneyConcentrationRequest
from reports.pojos.marketlevels.MarketLevelsRequest import MarketLevelsRequest
from reports.Constants import (
    LOG_PREFIX_SMART_MONEY_CONCENTRATION,
    LOG_PREFIX_MARKET_LEVELS,
)

logger = logging.getLogger(__name__)


# ==================== Response Helpers ====================

def buildErrorResponse(message: str, httpStatus: int) -> Response:
    """Build standardized error response."""
    return Response({'success': False, 'errorMessage': message}, status=httpStatus)


def buildSuccessResponse(data: dict) -> Response:
    """Build standardized success response."""
    return Response(data, status=status.HTTP_200_OK)


# ==================== Request Helpers ====================

def parseQueryParams(queryParams: dict) -> dict:
    """
    Parse query parameters into request data dict.
    Converts string values to appropriate types.
    """
    data = {}
    
    if 'pnlPeriod' in queryParams:
        data['pnlPeriod'] = int(queryParams['pnlPeriod'])
    if 'minWalletPnl' in queryParams:
        data['minWalletPnl'] = float(queryParams['minWalletPnl'])
    if 'minInvestmentAmount' in queryParams:
        data['minInvestmentAmount'] = float(queryParams['minInvestmentAmount'])
    if 'category' in queryParams:
        data['category'] = queryParams['category']
    if 'endDateFrom' in queryParams:
        data['endDateFrom'] = queryParams['endDateFrom']
    if 'endDateTo' in queryParams:
        data['endDateTo'] = queryParams['endDateTo']
    if 'limit' in queryParams:
        data['limit'] = int(queryParams['limit'])
    if 'offset' in queryParams:
        data['offset'] = int(queryParams['offset'])
    
    return data


def parseAndValidateRequest(requestData: dict) -> tuple[SmartMoneyConcentrationRequest, str]:
    """
    Parse and validate request data.
    
    Returns:
        Tuple of (request, errorMessage). errorMessage is None if valid.
    """
    reportRequest = SmartMoneyConcentrationRequest.fromDict(requestData or {})
    isValid, errorMessage = reportRequest.validate()
    return reportRequest, errorMessage if not isValid else None


def logConcentrationRequest(reportRequest: SmartMoneyConcentrationRequest) -> None:
    """Log incoming concentration API request."""
    logger.info("%s :: Request | Period: %d | MinPnL: %.0f | MinInvest: %.0f | Category: %s",
               LOG_PREFIX_SMART_MONEY_CONCENTRATION, reportRequest.pnlPeriod, float(reportRequest.minWalletPnl),
               float(reportRequest.minInvestmentAmount), reportRequest.category or "All")


def logConcentrationResponse(reportResponse) -> None:
    """Log concentration API response."""
    logger.info("%s :: Response | Markets: %d | Time: %.3fs",
               LOG_PREFIX_SMART_MONEY_CONCENTRATION, reportResponse.totalMarketsFound, reportResponse.executionTimeSeconds)


# ==================== Smart Money Concentration Endpoint ====================

@api_view(['GET'])
def getSmartMoneyConcentration(request: Request) -> Response:
    """
    Get smart money concentration report showing markets with highest 
    investment from qualifying smart wallets.
    
    Endpoint: GET /api/reports/smartmoney/concentration
    
    Query Parameters:
        pnlPeriod: int           - Period in days (30, 60, 90). Default: 30
        minWalletPnl: float      - Minimum PnL for qualifying wallets. Default: 10000
        minInvestmentAmount: float - Minimum investment per wallet in market. Default: 1000
        category: str            - Optional: Filter by wallet category
        endDateFrom: str         - Optional: Filter positions ending after this date (YYYY-MM-DD)
        endDateTo: str           - Optional: Filter positions ending before this date (YYYY-MM-DD)
        limit: int               - Pagination limit (1-1000). Default: 100
        offset: int              - Pagination offset. Default: 0
    
    Note: Only open positions with future end dates are included.
    """
    try:
        requestData = parseQueryParams(request.query_params)
        reportRequest, validationError = parseAndValidateRequest(requestData)
        
        if validationError:
            logger.info("%s :: Invalid request: %s", LOG_PREFIX_SMART_MONEY_CONCENTRATION, validationError)
            return buildErrorResponse(validationError, status.HTTP_400_BAD_REQUEST)
        
        logConcentrationRequest(reportRequest)
        
        reportResponse = SmartMoneyConcentrationGenerator.generate(reportRequest)
        
        if not reportResponse.success:
            logger.info("%s :: Generation failed: %s", LOG_PREFIX_SMART_MONEY_CONCENTRATION, reportResponse.errorMessage)
            return buildErrorResponse(reportResponse.errorMessage, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logConcentrationResponse(reportResponse)
        return buildSuccessResponse(reportResponse.toDict())
        
    except ValueError as e:
        logger.info("%s :: Invalid parameter: %s", LOG_PREFIX_SMART_MONEY_CONCENTRATION, str(e))
        return buildErrorResponse(f"Invalid parameter: {str(e)}", status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.exception("%s :: Unexpected error: %s", LOG_PREFIX_SMART_MONEY_CONCENTRATION, str(e))
        return buildErrorResponse(f"Internal server error: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== Market Levels Endpoint ====================

@api_view(['GET'])
def getMarketLevels(request: Request, marketId: int) -> Response:
    """
    Get buying level distribution for a specific market.
    
    Shows the average entry price distribution of all wallets holding 
    open positions in this market, segregated by outcome.
    
    Endpoint: GET /api/reports/smartmoney/concentration/market/{marketId}/levels
    
    Path Parameters:
        marketId: int - The market ID to analyze
    
    Response:
        - Market metadata (question, slug, conditionId)
        - For each outcome (Yes/No):
          - 10 price range buckets (0.0-0.1, 0.1-0.2, ..., 0.9-1.0)
          - Each bucket contains: totalAmountInvested, positionCount, walletCount
    
    Note: Only open positions with future end dates are included.
    """
    try:
        reportRequest = MarketLevelsRequest(marketId=marketId)
        isValid, validationError = reportRequest.validate()
        
        if not isValid:
            logger.info("%s :: Invalid request: %s", LOG_PREFIX_MARKET_LEVELS, validationError)
            return buildErrorResponse(validationError, status.HTTP_400_BAD_REQUEST)
        
        logger.info("%s :: Request | MarketId: %d", LOG_PREFIX_MARKET_LEVELS, marketId)
        
        reportResponse = MarketLevelsGenerator.generate(reportRequest)
        
        if not reportResponse.success:
            # Check if it's a "not found" error
            if "not found" in (reportResponse.errorMessage or "").lower():
                return buildErrorResponse(reportResponse.errorMessage, status.HTTP_404_NOT_FOUND)
            logger.info("%s :: Generation failed: %s", LOG_PREFIX_MARKET_LEVELS, reportResponse.errorMessage)
            return buildErrorResponse(reportResponse.errorMessage, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.info(
            "%s :: Response | MarketId: %d | Outcomes: %d | Positions: %d | Time: %.3fs",
            LOG_PREFIX_MARKET_LEVELS,
            marketId,
            len(reportResponse.outcomes),
            reportResponse.totalPositionCount,
            reportResponse.executionTimeSeconds
        )
        
        return buildSuccessResponse(reportResponse.toDict())
        
    except ValueError as e:
        logger.info("%s :: Invalid parameter: %s", LOG_PREFIX_MARKET_LEVELS, str(e))
        return buildErrorResponse(f"Invalid parameter: {str(e)}", status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.exception("%s :: Unexpected error: %s", LOG_PREFIX_MARKET_LEVELS, str(e))
        return buildErrorResponse(f"Internal server error: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
