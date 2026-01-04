"""
Generator for Market Report.

Responsibilities:
1. Execute query via MarketReportQuery
2. Fetch market data from database and Polymarket API
3. Aggregate position-level data by wallet
4. Build wallet positions with outcomes and PnL ranges
5. Build response object

Performance Optimizations:
- Single pass aggregation using dictionaries
- O(n) time complexity for n positions
- O(w) space complexity for w wallets
"""
import logging
import time
from typing import Dict, List, Optional
from decimal import Decimal
from collections import defaultdict

from reports.queries.MarketReportQuery import MarketReportQuery
from reports.pojos.marketreport.MarketReportRequest import MarketReportRequest
from reports.pojos.marketreport.MarketReportResponse import MarketReportResponse
from reports.pojos.marketreport.WalletPosition import WalletPosition
from reports.pojos.marketreport.OutcomePosition import OutcomePosition
from reports.pojos.marketreport.PnlRange import PnlRange
from markets.models import Market
from markets.implementations.polymarket.MarketsAPI import MarketsAPI

logger = logging.getLogger(__name__)

LOG_PREFIX = "[MARKET_REPORT_GENERATOR]"


class MarketReportGenerator:
    """
    Generates market report from position and wallet data.

    Aggregates positions by wallet and builds comprehensive report
    including market info from DB and Polymarket API.
    """

    @staticmethod
    def generate(request: MarketReportRequest) -> MarketReportResponse:
        """
        Generate the market report.

        Args:
            request: Report request parameters

        Returns:
            MarketReportResponse with market info and wallet positions
        """
        startTime = time.time()

        try:
            # Step 1: Validate
            validationError = MarketReportGenerator.validateRequest(request)
            if validationError:
                return MarketReportResponse.error(validationError)

            # Step 2: Fetch market data from database
            market = MarketReportGenerator.fetchMarketFromDB(request.marketId)
            if not market:
                return MarketReportResponse.error(f"Market with ID {request.marketId} not found")

            # Step 3: Fetch position data
            positionDataRows = MarketReportGenerator.fetchPositionData(request)

            # Step 4: Fetch market data from Polymarket API
            marketApiData = MarketReportGenerator.fetchMarketFromAPI(market.marketslug)

            # Step 5: Build market info dictionary
            marketInfo = MarketReportGenerator.buildMarketInfo(market, marketApiData)

            # Step 6: Handle empty results
            if not positionDataRows:
                return MarketReportGenerator.buildEmptyResponse(marketInfo, startTime)

            # Step 7: Aggregate positions by wallet
            walletPositions = MarketReportGenerator.aggregateByWallet(positionDataRows, marketApiData)

            # Step 8: Build and return response
            return MarketReportGenerator.buildSuccessResponse(
                marketInfo=marketInfo,
                wallets=walletPositions,
                startTime=startTime
            )

        except Exception as e:
            return MarketReportGenerator.handleError(e, startTime)

    # ==================== Validation ====================

    @staticmethod
    def validateRequest(request: MarketReportRequest) -> Optional[str]:
        """
        Validate request parameters.

        Returns:
            Error message if invalid, None if valid
        """
        isValid, errorMessage = request.validate()
        if not isValid:
            logger.info("%s :: Invalid request: %s", LOG_PREFIX, errorMessage)
            return errorMessage

        logger.info("%s :: Generating | MarketId: %d", LOG_PREFIX, request.marketId)
        return None

    # ==================== Data Fetching ====================

    @staticmethod
    def fetchMarketFromDB(marketId: int) -> Optional[Market]:
        """Fetch market from database."""
        try:
            return Market.objects.get(marketsid=marketId)
        except Market.DoesNotExist:
            logger.info("%s :: Market not found in DB | MarketId: %d", LOG_PREFIX, marketId)
            return None

    @staticmethod
    def fetchPositionData(request: MarketReportRequest) -> List[Dict]:
        """Fetch position data from query."""
        return MarketReportQuery.execute(request)

    @staticmethod
    def fetchMarketFromAPI(marketSlug: str) -> Optional[dict]:
        """Fetch market data from Polymarket API."""
        try:
            marketsAPI = MarketsAPI()
            marketResponse = marketsAPI.getMarketBySlug(marketSlug)
            if marketResponse:
                logger.info("%s :: Fetched market from API | Slug: %s", LOG_PREFIX, marketSlug)
                return {
                    'description': marketResponse.description,
                    'liquidity': marketResponse.liquidity,
                    'volume': marketResponse.volume,
                    'outcomePrices': marketResponse.outcomePrices,
                    'outcomes': marketResponse.outcomes,
                    'startDateIso': marketResponse.startDateIso,
                    'endDateIso': marketResponse.endDateIso
                }
            return None
        except Exception as e:
            logger.warning("%s :: Failed to fetch market from API | Slug: %s | Error: %s",
                         LOG_PREFIX, marketSlug, str(e))
            return None

    # ==================== Market Info Building ====================

    @staticmethod
    def buildMarketInfo(market: Market, apiData: Optional[dict]) -> dict:
        """Build market information dictionary from DB and API data."""
        marketInfo = {
            'question': market.question,
            'market_slug': market.marketslug
        }

        # Add API data if available
        if apiData:
            marketInfo['description'] = apiData.get('description', '')
            marketInfo['liquidity'] = float(apiData.get('liquidity', 0))
            marketInfo['volume'] = float(apiData.get('volume', 0))
            marketInfo['start_date'] = apiData.get('startDateIso')
            marketInfo['end_date'] = apiData.get('endDateIso')
        else:
            # Fallback to DB data
            marketInfo['description'] = ''
            marketInfo['liquidity'] = float(market.liquidity)
            marketInfo['volume'] = float(market.volume)
            marketInfo['start_date'] = market.startdate.isoformat() if market.startdate else None
            marketInfo['end_date'] = market.enddate.isoformat() if market.enddate else None

        return marketInfo

    # ==================== Aggregation ====================

    @staticmethod
    def aggregateByWallet(positionDataRows: List[Dict], marketApiData: Optional[dict]) -> List[WalletPosition]:
        """
        Aggregate position-level data by wallet.

        Groups positions by wallet and outcome, builds PnL ranges,
        and creates WalletPosition objects.

        Time Complexity: O(n) where n = number of position rows
        Space Complexity: O(w) where w = number of unique wallets
        """
        # Group positions by wallet
        walletData: Dict[int, Dict] = defaultdict(lambda: {
            'proxy_wallet': None,
            'positions': [],
            'pnl_30': {},
            'pnl_60': {},
            'pnl_90': {}
        })

        for row in positionDataRows:
            walletId = row['walletsid']

            # Store wallet info
            if not walletData[walletId]['proxy_wallet']:
                walletData[walletId]['proxy_wallet'] = row['proxywallet']

                # Store PnL data for each period
                walletData[walletId]['pnl_30'] = {
                    'invested': row.get('pnl_30_invested'),
                    'amount_out': row.get('pnl_30_amount_out'),
                    'current_value': row.get('pnl_30_current_value'),
                    'realized_win_rate': row.get('pnl_30_realized_win_rate'),
                    'realized_win_rate_odds': row.get('pnl_30_realized_win_rate_odds'),
                    'unrealized_win_rate': row.get('pnl_30_unrealized_win_rate'),
                    'unrealized_win_rate_odds': row.get('pnl_30_unrealized_win_rate_odds')
                }

                walletData[walletId]['pnl_60'] = {
                    'invested': row.get('pnl_60_invested'),
                    'amount_out': row.get('pnl_60_amount_out'),
                    'current_value': row.get('pnl_60_current_value'),
                    'realized_win_rate': row.get('pnl_60_realized_win_rate'),
                    'realized_win_rate_odds': row.get('pnl_60_realized_win_rate_odds'),
                    'unrealized_win_rate': row.get('pnl_60_unrealized_win_rate'),
                    'unrealized_win_rate_odds': row.get('pnl_60_unrealized_win_rate_odds')
                }

                walletData[walletId]['pnl_90'] = {
                    'invested': row.get('pnl_90_invested'),
                    'amount_out': row.get('pnl_90_amount_out'),
                    'current_value': row.get('pnl_90_current_value'),
                    'realized_win_rate': row.get('pnl_90_realized_win_rate'),
                    'realized_win_rate_odds': row.get('pnl_90_realized_win_rate_odds'),
                    'unrealized_win_rate': row.get('pnl_90_unrealized_win_rate'),
                    'unrealized_win_rate_odds': row.get('pnl_90_unrealized_win_rate_odds')
                }

            # Add position to wallet
            walletData[walletId]['positions'].append(row)

        # Build WalletPosition objects
        walletPositions = []
        for walletId, data in walletData.items():
            walletPosition = MarketReportGenerator.buildWalletPosition(
                walletId=walletId,
                data=data,
                marketApiData=marketApiData
            )
            walletPositions.append(walletPosition)

        return walletPositions

    @staticmethod
    def buildWalletPosition(walletId: int, data: Dict, marketApiData: Optional[dict]) -> WalletPosition:
        """Build a WalletPosition object from aggregated data."""
        positions = data['positions']

        # Calculate wallet-level PnL (using market-wise calculated values from first position)
        # Since calculated values are market-wise, they're the same across all positions for this wallet
        firstPosition = positions[0]
        calculatedAmountInvested = Decimal(str(firstPosition.get('calculatedamountinvested', 0)))
        calculatedAmountOut = Decimal(str(firstPosition.get('calculatedamountout', 0)))
        calculatedCurrentValue = Decimal(str(firstPosition.get('calculatedcurrentvalue', 0)))

        pnl = (calculatedCurrentValue + calculatedAmountOut) - calculatedAmountInvested
        pnlPercentage = (pnl / calculatedAmountInvested * 100) if calculatedAmountInvested > 0 else Decimal('0')

        # Create wallet position
        walletPosition = WalletPosition(
            proxyWallet=data['proxy_wallet'],
            calculatedAmountInvested=calculatedAmountInvested,
            calculatedAmountOut=calculatedAmountOut,
            calculatedCurrentValue=calculatedCurrentValue,
            pnl=pnl,
            pnlPercentage=pnlPercentage
        )

        # Add PnL ranges
        for period in [30, 60, 90]:
            pnlData = data[f'pnl_{period}']
            if pnlData['invested'] is not None:
                invested = Decimal(str(pnlData['invested'] or 0))
                amountOut = Decimal(str(pnlData['amount_out'] or 0))
                currentValue = Decimal(str(pnlData['current_value'] or 0))
                periodPnl = (currentValue + amountOut) - invested

                pnlRange = PnlRange(
                    range=period,
                    pnl=periodPnl,
                    realizedWinRate=Decimal(str(pnlData['realized_win_rate'] or 0)),
                    realizedWinRateOdds=pnlData['realized_win_rate_odds'] or '',
                    unrealizedWinRate=Decimal(str(pnlData['unrealized_win_rate'] or 0)),
                    unrealizedWinRateOdds=pnlData['unrealized_win_rate_odds'] or ''
                )
                walletPosition.addPnlRange(pnlRange)

        # Get current prices from API if available
        currentPrices = MarketReportGenerator.getCurrentPrices(marketApiData)

        # Add outcome positions
        for position in positions:
            outcome = position['outcome']
            positionStatus = position['positionstatus']
            positionType = 'open' if positionStatus == 1 else 'closed'

            # Get current price for this outcome
            currentPrice = currentPrices.get(outcome, Decimal('0'))

            outcomePosition = OutcomePosition(
                outcome=outcome,
                currentPrice=currentPrice,
                avgPrice=Decimal(str(position.get('averageentryprice', 0))),
                positionType=positionType,
                amountSpent=Decimal(str(position.get('amountspent', 0))),
                totalShares=Decimal(str(position.get('totalshares', 0))),
                currentShares=Decimal(str(position.get('currentshares', 0))),
                amountRemaining=Decimal(str(position.get('amountremaining', 0)))
            )
            walletPosition.addOutcome(outcomePosition)

        return walletPosition

    @staticmethod
    def getCurrentPrices(marketApiData: Optional[dict]) -> Dict[str, Decimal]:
        """Extract current prices from API data, mapping outcome names to prices."""
        currentPrices = {}

        if marketApiData and 'outcomes' in marketApiData and 'outcomePrices' in marketApiData:
            outcomes = marketApiData['outcomes']
            prices = marketApiData['outcomePrices']

            for i, outcome in enumerate(outcomes):
                if i < len(prices):
                    currentPrices[outcome] = Decimal(str(prices[i]))

        return currentPrices

    # ==================== Response Building ====================

    @staticmethod
    def buildEmptyResponse(marketInfo: dict, startTime: float) -> MarketReportResponse:
        """Build response when no position data is found."""
        executionTime = time.time() - startTime
        logger.info("%s :: No positions found | Time: %.3fs", LOG_PREFIX, executionTime)

        return MarketReportResponse.success(
            market=marketInfo,
            wallets=[],
            executionTimeSeconds=executionTime
        )

    @staticmethod
    def buildSuccessResponse(
        marketInfo: dict,
        wallets: List[WalletPosition],
        startTime: float
    ) -> MarketReportResponse:
        """Build successful response with aggregated data."""
        executionTime = time.time() - startTime

        logger.info("%s :: Generated | Wallets: %d | Time: %.3fs",
                   LOG_PREFIX, len(wallets), executionTime)

        return MarketReportResponse.success(
            market=marketInfo,
            wallets=wallets,
            executionTimeSeconds=executionTime
        )

    # ==================== Error Handling ====================

    @staticmethod
    def handleError(error: Exception, startTime: float) -> MarketReportResponse:
        """Handle and log generation errors."""
        executionTime = time.time() - startTime
        logger.exception("%s :: Failed | Time: %.3fs | Error: %s", LOG_PREFIX, executionTime, str(error))
        return MarketReportResponse.error(f"Report generation failed: {str(error)}")
