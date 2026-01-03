// Market and Position Types
export interface Market {
  id: string
  question: string
  slug: string
  endDate: string
  imageUrl?: string
}

export interface Position {
  id: string
  marketId: string
  walletAddress: string
  outcome: string
  shares: number
  avgPrice: number
  currentPrice: number
  pnl: number
  pnlPercent: number
}

export interface Wallet {
  address: string
  totalPnl: number
  totalPnlPercent: number
  positionCount: number
  category?: string
}

// API Response Types
export interface ApiResponse<T> {
  data: T
  success: boolean
  message?: string
}

export interface PaginatedResponse<T> {
  results: T[]
  count: number
  next: string | null
  previous: string | null
}

// Smart Money Concentration Types
export interface SmartMoneyConcentrationRequest {
  pnlPeriod: 30 | 60 | 90
  minWalletPnl: number
  minInvestmentAmount: number
  category?: string
  endDateFrom?: string  // ISO date string (YYYY-MM-DD)
  endDateTo?: string    // ISO date string (YYYY-MM-DD)
  limit?: number
  offset?: number
}

export interface SmartMoneyConcentrationResponse {
  success: boolean
  errorMessage?: string
  summary: SmartMoneyConcentrationSummary
  appliedFilters: SmartMoneyConcentrationFilters
  pagination: SmartMoneyConcentrationPagination
  executionTimeSeconds: number
  markets: SmartMoneyMarketConcentration[]
}

export interface SmartMoneyConcentrationSummary {
  totalMarketsFound: number
  totalQualifyingWallets: number
  totalInvestedAcrossMarkets: number
  totalCurrentValueAcrossMarkets: number
  unrealizedPnlAcrossMarkets: number
}

export interface SmartMoneyConcentrationFilters {
  pnlPeriod: number
  minWalletPnl: number
  minInvestmentAmount: number
  category?: string
}

export interface SmartMoneyConcentrationPagination {
  limit: number
  offset: number
  hasMore: boolean
  returnedCount: number
}

export interface SmartMoneyMarketConcentration {
  marketsId: number
  conditionId: string
  marketSlug: string
  question: string
  eventId: number
  eventSlug: string
  eventTitle: string
  volume: number
  liquidity: number
  endDate: string | null
  isOpen: boolean
  walletCount: number
  totalInvested: number
  totalCurrentValue: number
  totalAmountOut: number
  unrealizedPnl: number
  roiPercent: number
  outcomes: SmartMoneyOutcomeBreakdown[]
}

export interface SmartMoneyOutcomeBreakdown {
  outcome: string
  walletCount: number
  totalInvested: number
  totalCurrentValue: number
}

// Market Levels Types
export interface MarketLevelsResponse {
  success: boolean
  errorMessage?: string
  market: {
    marketId: number
    marketSlug: string
    question: string
    conditionId: string
  }
  summary: {
    totalPositionCount: number
    totalAmountInvested: number
    totalWalletCount: number
  }
  outcomes: MarketLevelsOutcome[]
  executionTimeSeconds: number
}

export interface MarketLevelsOutcome {
  outcome: string
  totalAmountInvested: number
  totalPositionCount: number
  totalWalletCount: number
  levels: PriceRangeLevel[]
}

export interface PriceRangeLevel {
  rangeStart: number
  rangeEnd: number
  rangeLabel: string
  totalAmountInvested: number
  positionCount: number
  walletCount: number
}

