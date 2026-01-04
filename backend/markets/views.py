"""
API views for markets.
"""
import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from dataclasses import asdict
from markets.implementations.polymarket.MarketsAPI import MarketsAPI
from markets.implementations.polymarket.Constants import LOG_PREFIX_MARKETS_API

logger = logging.getLogger(__name__)


@api_view(['GET'])
def getMarketBySlug(request, slug):
    """
    Get market details by slug.

    GET /api/markets/slug/{slug}

    Args:
        slug: Market slug identifier (from URL path)

    Returns:
        - 200: Market data as JSON
        - 404: Market not found
        - 500: Internal server error

    Example:
        GET /api/markets/slug/will-bitcoin-reach-100k-in-january-2026
    """
    try:
        logger.info("%s :: Market detail API called for slug: %s", LOG_PREFIX_MARKETS_API, slug)

        # Initialize API client and fetch market
        marketsAPI = MarketsAPI()
        market = marketsAPI.getMarketBySlug(slug)

        if market is None:
            logger.info("%s :: Market not found for slug: %s", LOG_PREFIX_MARKETS_API, slug)
            return Response(
                {'error': f'Market not found for slug: {slug}'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Convert POJO to dictionary for JSON serialization
        marketDict = asdict(market)

        logger.info("%s :: Market retrieved successfully | Slug: %s | ID: %s",
            LOG_PREFIX_MARKETS_API,
            slug,
            market.id
        )

        return Response(marketDict, status=status.HTTP_200_OK)

    except Exception as e:
        errorMessage = f"Failed to fetch market by slug: {str(e)}"
        logger.info("%s :: %s", LOG_PREFIX_MARKETS_API, errorMessage, exc_info=True)

        return Response(
            {'error': errorMessage},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
