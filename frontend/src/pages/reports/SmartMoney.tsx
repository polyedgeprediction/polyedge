import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { RefreshCw, AlertCircle, ServerOff, WifiOff, ChevronLeft, ChevronRight, Copy, Check, Search, Calendar as CalendarIcon, X, ChevronDown } from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { format, addDays } from 'date-fns'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { formatCurrencyCompact, formatDate } from '@/lib/formatters'
import { reports } from '@/lib/api'
import type {
  SmartMoneyConcentrationResponse,
  SmartMoneyConcentrationRequest,
  MarketLevelsResponse,
  MarketLevelsOutcome,
} from '@/types'

const CATEGORIES = [
  { value: 'all', label: 'All Categories' },
  { value: 'Politics', label: 'Politics' },
  { value: 'Sports', label: 'Sports' },
  { value: 'Crypto', label: 'Crypto' },
  { value: 'Finance', label: 'Finance' },
  { value: 'Culture', label: 'Culture' },
  { value: 'Tech', label: 'Tech' },
]

const PERIODS = [
  { value: '30', label: '30 Days' },
  { value: '60', label: '60 Days' },
  { value: '90', label: '90 Days' },
]

const END_DATE_OPTIONS = [
  { value: 'all', label: 'All Dates' },
  { value: '30', label: '30 Days' },
  { value: '60', label: '60 Days' },
  { value: '90', label: '90 Days' },
  { value: 'custom', label: 'Custom' },
]

// Error type detection
type ErrorType = 'connection' | 'server' | 'generic'

function getErrorType(error: string): ErrorType {
  const lowerError = error.toLowerCase()
  if (lowerError.includes('failed to fetch') || lowerError.includes('network') || lowerError.includes('econnrefused')) {
    return 'connection'
  }
  if (lowerError.includes('500') || lowerError.includes('502') || lowerError.includes('503') || lowerError.includes('504')) {
    return 'server'
  }
  return 'generic'
}

// Chart colors following design system
const CHART_COLORS = {
  Yes: '#22c55e', // profit green
  No: '#ef4444',  // loss red
  default: '#3b82f6', // accent blue
}

const getOutcomeColor = (outcome: string): string => {
  const upper = outcome.toUpperCase()
  if (upper === 'YES') return CHART_COLORS.Yes
  if (upper === 'NO') return CHART_COLORS.No
  return CHART_COLORS.default
}

// Format Y-axis values
const formatYAxis = (value: number): string => {
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`
  return `$${value}`
}

// Levels data state type
interface LevelsState {
  loading: boolean
  error: string | null
  data: MarketLevelsResponse | null
}

export default function SmartMoney() {
  
  // State
  const [data, setData] = useState<SmartMoneyConcentrationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filter state
  const [pnlPeriod, setPnlPeriod] = useState<30 | 60 | 90>(30)
  const [minWalletPnl, setMinWalletPnl] = useState(10000)
  const [minInvestmentAmount, setMinInvestmentAmount] = useState(1000)
  const [category, setCategory] = useState('all')
  
  // End date filter state
  const [endDateOption, setEndDateOption] = useState('all')
  const [customDateFrom, setCustomDateFrom] = useState<Date | undefined>(undefined)
  const [customDateTo, setCustomDateTo] = useState<Date | undefined>(undefined)

  // Pagination state (client-side)
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 10

  // Search state
  const [searchQuery, setSearchQuery] = useState('')

  // Expanded levels state
  const [expandedMarketId, setExpandedMarketId] = useState<number | null>(null)
  const [levelsData, setLevelsData] = useState<Record<number, LevelsState>>({})

  // Toggle levels dropdown
  const toggleLevels = useCallback(async (marketId: number) => {
    if (expandedMarketId === marketId) {
      // Collapse if already expanded
      setExpandedMarketId(null)
      return
    }

    // Expand this row
    setExpandedMarketId(marketId)

    // If we already have data for this market, don't refetch
    if (levelsData[marketId]?.data) {
      return
    }

    // Fetch levels data
    setLevelsData(prev => ({
      ...prev,
      [marketId]: { loading: true, error: null, data: null }
    }))

    try {
      const response = await reports.marketLevels(marketId)
      if (response.success) {
        setLevelsData(prev => ({
          ...prev,
          [marketId]: { loading: false, error: null, data: response }
        }))
      } else {
        setLevelsData(prev => ({
          ...prev,
          [marketId]: { loading: false, error: response.errorMessage || 'Failed to load levels', data: null }
        }))
      }
    } catch (err) {
      let errorMessage = 'Failed to fetch levels'
      if (err instanceof Error) {
        errorMessage = err.message
      }
      setLevelsData(prev => ({
        ...prev,
        [marketId]: { loading: false, error: errorMessage, data: null }
      }))
    }
  }, [expandedMarketId, levelsData])

  // Compute date range based on selected option
  const getDateRange = useCallback(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    
    if (endDateOption === 'all') {
      return { endDateFrom: undefined, endDateTo: undefined }
    }
    
    if (endDateOption === 'custom') {
      return {
        endDateFrom: customDateFrom ? format(customDateFrom, 'yyyy-MM-dd') : undefined,
        endDateTo: customDateTo ? format(customDateTo, 'yyyy-MM-dd') : undefined,
      }
    }
    
    // Preset options: 30, 60, 90 days from today
    const days = parseInt(endDateOption)
    const fromDate = today
    const toDate = addDays(today, days)
    
    return {
      endDateFrom: format(fromDate, 'yyyy-MM-dd'),
      endDateTo: format(toDate, 'yyyy-MM-dd'),
    }
  }, [endDateOption, customDateFrom, customDateTo])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const dateRange = getDateRange()
      const params: SmartMoneyConcentrationRequest = {
        pnlPeriod,
        minWalletPnl,
        minInvestmentAmount,
        category: category === 'all' ? undefined : category,
        endDateFrom: dateRange.endDateFrom,
        endDateTo: dateRange.endDateTo,
        limit: 100,
        offset: 0,
      }
      const response = await reports.smartMoneyConcentration(params)
      if (response.success) {
        setData(response)
        setError(null) // Clear any previous errors
      } else {
        // API returned an error response
        const errorMsg = response.errorMessage || 'Failed to load report'
        setError(errorMsg)
        setData(null) // Clear data on error
      }
    } catch (err) {
      // Handle network errors and other exceptions
      let errorMessage = 'Failed to fetch data'
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        errorMessage = 'Failed to fetch - Server may be offline'
      } else if (err instanceof Error) {
        errorMessage = err.message
      }
      console.error('SmartMoney fetch error:', err)
      setError(errorMessage)
      setData(null) // Clear data on error
    } finally {
      setLoading(false)
    }
  }, [pnlPeriod, minWalletPnl, minInvestmentAmount, category, getDateRange])

  // Initial load only
  useEffect(() => {
    fetchData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Set document title
  useEffect(() => {
    document.title = 'concentration'
    return () => {
      document.title = 'polyedge'
    }
  }, [])

  // Handle Apply button click
  const handleApplyFilters = () => {
    setCurrentPage(1)
    fetchData()
  }

  // Copied condition ID state
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const copyConditionId = async (e: React.MouseEvent, conditionId: string) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(conditionId)
      setCopiedId(conditionId)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  // Filter markets by search query
  const filteredMarkets = useMemo(() => {
    if (!data?.markets) return []
    if (!searchQuery.trim()) return data.markets
    
    const query = searchQuery.toLowerCase()
    return data.markets.filter(market => 
      market.question.toLowerCase().includes(query) ||
      market.eventTitle.toLowerCase().includes(query) ||
      market.marketSlug.toLowerCase().includes(query)
    )
  }, [data?.markets, searchQuery])

  // Reset page when search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery])

  // Always render something visible
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', minHeight: '400px', width: '100%', color: '#fafafa' }}>
      {/* Category Pills + Filters + Search */}
      <div className="flex items-center justify-between gap-4">
        <div className="inline-flex items-center gap-1 bg-elevated/50 border border-border-subtle rounded-lg p-1">
          {CATEGORIES.map((c) => (
            <button
              key={c.value}
              onClick={() => setCategory(c.value)}
              className={`px-3 h-7 text-xs rounded-md transition-colors ${
                category === c.value
                  ? 'bg-surface text-primary font-medium'
                  : 'text-muted hover:text-secondary hover:bg-surface/50'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="inline-flex items-center gap-px bg-elevated/50 border border-border-subtle rounded-lg p-1">
          {/* Period - compact */}
          <Select
            value={pnlPeriod.toString()}
            onValueChange={(v) => setPnlPeriod(parseInt(v) as 30 | 60 | 90)}
          >
            <SelectTrigger className="h-7 px-2 text-xs bg-transparent border-0 shadow-none focus:ring-0 gap-0.5 w-[80px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="w-px h-4 bg-border-subtle" />

          <div className="flex items-center gap-1.5 px-2">
            <span className="text-xs text-muted whitespace-nowrap">PnL ≥</span>
            <Input
              type="number"
              value={minWalletPnl}
              onChange={(e) => setMinWalletPnl(parseInt(e.target.value) || 0)}
              className="w-24 h-7 px-2 text-xs bg-surface border-border-subtle [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              min={0}
            />
          </div>

          <div className="w-px h-4 bg-border-subtle" />

          <div className="flex items-center gap-1.5 px-2">
            <span className="text-xs text-muted whitespace-nowrap">Inv ≥</span>
            <Input
              type="number"
              value={minInvestmentAmount}
              onChange={(e) => setMinInvestmentAmount(parseInt(e.target.value) || 0)}
              className="w-24 h-7 px-2 text-xs bg-surface border-border-subtle [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              min={0}
            />
          </div>

          <div className="w-px h-4 bg-border-subtle" />

          {/* End Date Filter */}
          <Popover>
            <PopoverTrigger asChild>
              <button className="flex items-center gap-1.5 h-7 px-2 text-xs hover:bg-surface/50 rounded-md transition-colors">
                <CalendarIcon className="w-3.5 h-3.5 text-muted" />
                <span className="text-xs text-muted">Ends:</span>
                <span className={`text-xs ${endDateOption === 'all' ? 'text-muted' : 'text-secondary'}`}>
                  {endDateOption === 'all' && 'All'}
                  {endDateOption === '30' && '30d'}
                  {endDateOption === '60' && '60d'}
                  {endDateOption === '90' && '90d'}
                  {endDateOption === 'custom' && (
                    customDateFrom && customDateTo 
                      ? `${format(customDateFrom, 'MMM d')} - ${format(customDateTo, 'MMM d')}`
                      : 'Custom'
                  )}
                </span>
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="end">
              <div className="p-2 space-y-2">
                <div className="flex flex-wrap gap-1">
                  {END_DATE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => {
                        setEndDateOption(opt.value)
                        if (opt.value !== 'custom') {
                          setCustomDateFrom(undefined)
                          setCustomDateTo(undefined)
                        }
                      }}
                      className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                        endDateOption === opt.value
                          ? 'bg-accent text-white font-medium'
                          : 'bg-elevated hover:bg-surface text-secondary'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                
                {endDateOption === 'custom' && (
                  <div className="border-t border-border-subtle pt-2 space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="flex-1">
                        <div className="text-xs text-muted mb-1">From</div>
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button
                              variant="outline"
                              size="sm"
                              className="w-full h-7 text-xs justify-start"
                            >
                              <CalendarIcon className="w-3.5 h-3.5 mr-1.5" />
                              {customDateFrom ? format(customDateFrom, 'MMM d, yyyy') : 'Select'}
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-auto p-0" align="start">
                            <Calendar
                              mode="single"
                              selected={customDateFrom}
                              onSelect={setCustomDateFrom}
                              disabled={{ before: new Date() }}
                              initialFocus
                            />
                          </PopoverContent>
                        </Popover>
                      </div>
                      <div className="flex-1">
                        <div className="text-xs text-muted mb-1">To</div>
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button
                              variant="outline"
                              size="sm"
                              className="w-full h-7 text-xs justify-start"
                            >
                              <CalendarIcon className="w-3.5 h-3.5 mr-1.5" />
                              {customDateTo ? format(customDateTo, 'MMM d, yyyy') : 'Select'}
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-auto p-0" align="start">
                            <Calendar
                              mode="single"
                              selected={customDateTo}
                              onSelect={setCustomDateTo}
                              disabled={customDateFrom ? { before: customDateFrom } : { before: new Date() }}
                              initialFocus
                            />
                          </PopoverContent>
                        </Popover>
                      </div>
                    </div>
                    {customDateFrom && customDateTo && (
                      <button
                        onClick={() => {
                          setCustomDateFrom(undefined)
                          setCustomDateTo(undefined)
                        }}
                        className="flex items-center gap-1 text-xs text-muted hover:text-secondary"
                      >
                        <X className="w-3.5 h-3.5" />
                        Clear dates
                      </button>
                    )}
                  </div>
                )}
              </div>
            </PopoverContent>
          </Popover>

          <div className="w-px h-4 bg-border-subtle" />

          {/* Search */}
          <div className="flex items-center gap-1.5 px-2">
            <Search className="w-3.5 h-3.5 text-muted flex-shrink-0" />
            <Input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search..."
              className="w-40 h-6 px-2 text-xs bg-surface border-border-subtle"
            />
          </div>

          <div className="w-px h-4 bg-border-subtle" />

          <Button 
            onClick={handleApplyFilters} 
            size="sm" 
            disabled={loading} 
            className="h-7 px-3 text-xs bg-accent hover:bg-accent-hover text-white"
          >
            {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : 'Apply'}
          </Button>
        </div>
      </div>

      {/* Error State - Show immediately when error occurs */}
      {error && !loading && (
        <Card>
          <CardContent style={{ padding: '48px 24px', textAlign: 'center' }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px'
            }}>
              {getErrorType(error) === 'connection' ? (
                <WifiOff style={{ width: '32px', height: '32px', color: '#ef4444' }} />
              ) : getErrorType(error) === 'server' ? (
                <ServerOff style={{ width: '32px', height: '32px', color: '#ef4444' }} />
              ) : (
                <AlertCircle style={{ width: '32px', height: '32px', color: '#ef4444' }} />
              )}
            </div>
            
            {getErrorType(error) === 'connection' ? (
              <>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>
                  Cannot Connect to Server
                </h3>
                <p style={{ fontSize: '14px', color: '#a1a1aa', marginBottom: '4px', maxWidth: '400px', margin: '0 auto 4px' }}>
                  Unable to reach the backend server. Please make sure the server is running.
                </p>
                <p style={{ fontSize: '12px', color: '#71717a', marginBottom: '24px', fontFamily: 'monospace' }}>
                  Run: cd backend && python manage.py runserver
                </p>
              </>
            ) : getErrorType(error) === 'server' ? (
              <>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>
                  Server Error
                </h3>
                <p style={{ fontSize: '14px', color: '#a1a1aa', marginBottom: '4px', maxWidth: '600px', margin: '0 auto 4px' }}>
                  The server encountered an error while processing your request.
                </p>
                <div style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  margin: '16px auto 24px',
                  maxWidth: '600px',
                  fontSize: '13px',
                  color: '#fca5a5',
                  fontFamily: 'monospace',
                  textAlign: 'left',
                  wordBreak: 'break-word'
                }}>
                  {error}
                </div>
              </>
            ) : (
              <>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', marginBottom: '8px' }}>
                  Error Loading Data
                </h3>
                <div style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  margin: '16px auto 24px',
                  maxWidth: '600px',
                  fontSize: '14px',
                  color: '#fca5a5',
                  wordBreak: 'break-word'
                }}>
                  {error}
                </div>
              </>
            )}
            
            <Button onClick={fetchData} variant="outline">
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading State - Show when loading and no error */}
      {loading && !error && (
        <Card>
          <CardContent style={{ padding: '48px 24px', textAlign: 'center' }}>
            <RefreshCw className="w-8 h-8 animate-spin" style={{ margin: '0 auto 16px', color: '#a1a1aa' }} />
            <p style={{ fontSize: '14px', color: '#a1a1aa', margin: 0 }}>Loading smart money data...</p>
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!loading && !error && data && data.markets.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center justify-center text-center">
              <AlertCircle className="w-12 h-12 text-muted mb-4" />
              <h3 className="text-lg font-medium text-primary mb-1">No markets found</h3>
              <p className="text-sm text-muted mb-4">
                No markets match your current filter criteria. Try adjusting the filters.
              </p>
              <Button
                variant="outline"
                onClick={() => {
                  setPnlPeriod(30)
                  setMinWalletPnl(10000)
                  setMinInvestmentAmount(1000)
                  setCategory('all')
                }}
              >
                Reset filters
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Markets Table */}
      {!loading && !error && data && filteredMarkets.length > 0 && (() => {
        const totalPages = Math.ceil(filteredMarkets.length / pageSize)
        const startIdx = (currentPage - 1) * pageSize
        const endIdx = startIdx + pageSize
        const paginatedMarkets = filteredMarkets.slice(startIdx, endIdx)
        
        return (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="text-left text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
                      Market
                    </th>
                    <th className="text-left text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
                      Outcomes
                    </th>
                    <th className="text-center text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
                      Wallets
                    </th>
                    <th className="text-right text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
                      Invested / Out
                    </th>
                    <th className="text-right text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
                      Current
                    </th>
                    <th className="text-center text-xs font-medium text-muted uppercase tracking-wide py-3 px-4">
                      End Date
                    </th>
                    <th className="text-center text-xs font-medium text-muted uppercase tracking-wide py-3 px-4 w-20">
                      Levels
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {paginatedMarkets.map((market) => (
                      <React.Fragment key={market.marketsId}>
                        <tr className="hover:bg-elevated/50 transition-colors group">
                          <td className="py-3 px-4">
                            <div className="max-w-md">
                              <div className="flex items-center gap-2">
                                <span 
                                  className="text-sm text-primary font-medium hover:text-accent cursor-pointer"
                                  onClick={(e) => copyConditionId(e, market.conditionId)}
                                  title="Click to copy condition ID"
                                >
                                  {market.question}
                                </span>
                                {copiedId === market.conditionId ? (
                                  <Check className="w-3 h-3 text-profit flex-shrink-0" />
                                ) : (
                                  <Copy className="w-3 h-3 text-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                                )}
                              </div>
                              <div className="text-xs text-muted mt-0.5">
                                {market.eventTitle}
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex flex-col gap-1">
                              {market.outcomes.map((outcome) => (
                                <div key={outcome.outcome} className="flex items-center gap-1.5 text-sm font-mono">
                                  <span className={`font-medium ${
                                    outcome.outcome.toUpperCase() === 'YES'
                                      ? 'text-profit'
                                      : outcome.outcome.toUpperCase() === 'NO'
                                      ? 'text-loss'
                                      : 'text-primary'
                                  }`}>
                                    {outcome.outcome}:
                                  </span>
                                  <span className="text-primary tabular-nums">
                                    {formatCurrencyCompact(outcome.totalInvested)}/{formatCurrencyCompact(outcome.totalCurrentValue)}
                                  </span>
                                  <span className="text-primary">[{outcome.walletCount}]</span>
                                </div>
                              ))}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-sm font-mono tabular-nums text-center text-primary">
                            {market.walletCount}
                          </td>
                          <td className="py-3 px-4 text-sm font-mono tabular-nums text-right text-primary">
                            {formatCurrencyCompact(market.totalInvested)}/{formatCurrencyCompact(market.totalAmountOut)}
                          </td>
                          <td className="py-3 px-4 text-sm font-mono tabular-nums text-right text-primary">
                            {formatCurrencyCompact(market.totalCurrentValue)}
                          </td>
                          <td className="py-3 px-4 text-sm font-mono tabular-nums text-center text-primary">
                            {formatDate(market.endDate)}
                          </td>
                          <td className="py-3 px-4 text-center">
                            <Button
                              variant="ghost"
                              size="sm"
                              className={`h-7 w-7 p-0 hover:bg-accent/10 transition-transform ${expandedMarketId === market.marketsId ? 'rotate-180' : ''}`}
                              onClick={() => toggleLevels(market.marketsId)}
                              title={expandedMarketId === market.marketsId ? "Hide buying levels" : "View buying levels"}
                            >
                              <ChevronDown className="w-4 h-4 text-accent" />
                            </Button>
                          </td>
                        </tr>
                        {/* Expanded Levels Row */}
                        {expandedMarketId === market.marketsId && (
                          <tr>
                            <td colSpan={7} className="p-0">
                              <div className="bg-elevated/30 border-t border-b border-border-subtle">
                                {/* Loading State */}
                                {levelsData[market.marketsId]?.loading && (
                                  <div className="flex items-center justify-center py-8">
                                    <RefreshCw className="w-5 h-5 animate-spin text-muted" />
                                    <span className="ml-2 text-sm text-muted">Loading levels...</span>
                                  </div>
                                )}

                                {/* Error State */}
                                {levelsData[market.marketsId]?.error && (
                                  <div className="flex items-center justify-center py-8 text-loss">
                                    <AlertCircle className="w-5 h-5" />
                                    <span className="ml-2 text-sm">{levelsData[market.marketsId].error}</span>
                                  </div>
                                )}

                                {/* Levels Data */}
                                {levelsData[market.marketsId]?.data && (() => {
                                  const levelsInfo = levelsData[market.marketsId].data!
                                  const outcomesWithInvestment = levelsInfo.outcomes.filter(o => o.totalAmountInvested > 0)
                                  const outcomeChartData = outcomesWithInvestment.map((outcome: MarketLevelsOutcome) => ({
                                    outcome: outcome.outcome,
                                    data: outcome.levels.map(level => ({
                                      rangeLabel: level.rangeLabel,
                                      totalAmountInvested: level.totalAmountInvested,
                                    }))
                                  }))

                                  return (
                                    <div className="p-4">
                                      {/* Charts */}
                                      {outcomeChartData.length > 0 ? (
                                        <div className={`grid gap-4 ${outcomeChartData.length === 1 ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-2'}`}>
                                          {outcomeChartData.map((outcomeChart) => {
                                            const outcome = outcomesWithInvestment.find(o => o.outcome === outcomeChart.outcome)!
                                            return (
                                              <div key={outcomeChart.outcome} className="bg-surface border border-border-subtle rounded-lg p-4">
                                                <div className="flex items-center justify-between mb-3">
                                                  <span
                                                    className="text-sm font-medium"
                                                    style={{ color: getOutcomeColor(outcomeChart.outcome) }}
                                                  >
                                                    {outcomeChart.outcome}
                                                  </span>
                                                  <div className="flex items-center gap-1.5 text-sm font-mono">
                                                    <span className="text-primary tabular-nums">{formatCurrencyCompact(outcome.totalAmountInvested)}</span>
                                                    <span className="text-primary">[{outcome.totalWalletCount}]</span>
                                                  </div>
                                                </div>
                                                <div className="h-[200px] w-full">
                                                  <ResponsiveContainer width="100%" height="100%">
                                                    <BarChart
                                                      data={outcomeChart.data}
                                                      margin={{ top: 10, right: 10, left: 10, bottom: 10 }}
                                                    >
                                                      <XAxis
                                                        dataKey="rangeLabel"
                                                        stroke="#71717a"
                                                        fontSize={10}
                                                        tickLine={false}
                                                        axisLine={false}
                                                        tick={{ fill: '#a1a1aa' }}
                                                      />
                                                      <YAxis
                                                        stroke="#71717a"
                                                        fontSize={10}
                                                        tickLine={false}
                                                        axisLine={false}
                                                        tickFormatter={formatYAxis}
                                                        tick={{ fill: '#a1a1aa' }}
                                                        width={50}
                                                      />
                                                      <Tooltip
                                                        content={({ active, payload, label }) => {
                                                          if (!active || !payload || payload.length === 0) return null
                                                          return (
                                                            <div className="bg-surface border border-border-subtle rounded-lg p-2 shadow-lg">
                                                              <p className="text-xs text-muted mb-1">Price Range: {label}</p>
                                                              <div className="flex items-center justify-between gap-3">
                                                                <span
                                                                  className="text-xs font-medium"
                                                                  style={{ color: getOutcomeColor(outcomeChart.outcome) }}
                                                                >
                                                                  {outcomeChart.outcome}
                                                                </span>
                                                                <span className="text-xs font-mono tabular-nums text-primary">
                                                                  {formatCurrencyCompact(payload[0].value as number)}
                                                                </span>
                                                              </div>
                                                            </div>
                                                          )
                                                        }}
                                                      />
                                                      <Bar
                                                        dataKey="totalAmountInvested"
                                                        fill={getOutcomeColor(outcomeChart.outcome)}
                                                        radius={[4, 4, 0, 0]}
                                                        maxBarSize={40}
                                                      >
                                                        {outcomeChart.data.map((_, index) => (
                                                          <Cell
                                                            key={`cell-${index}`}
                                                            fill={getOutcomeColor(outcomeChart.outcome)}
                                                            fillOpacity={0.85}
                                                          />
                                                        ))}
                                                      </Bar>
                                                    </BarChart>
                                                  </ResponsiveContainer>
                                                </div>
                                              </div>
                                            )
                                          })}
                                        </div>
                                      ) : (
                                        <div className="flex items-center justify-center py-6 text-muted text-sm">
                                          No position data available
                                        </div>
                                      )}

                                      {/* Execution time */}
                                      <div className="text-xs text-muted text-right mt-3">
                                        Loaded in {levelsInfo.executionTimeSeconds.toFixed(3)}s
                                      </div>
                                    </div>
                                  )
                                })()}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                </tbody>
              </table>
            </div>
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-border-subtle">
                <span className="text-xs text-muted">
                  {startIdx + 1}–{Math.min(endIdx, filteredMarkets.length)} of {filteredMarkets.length}
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <span className="text-xs text-secondary px-2">
                    {currentPage} / {totalPages}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        )
      })()}

      {/* Execution time footer */}
      {data && !loading && (
        <div className="text-xs text-muted text-right">
          Query executed in {data.executionTimeSeconds.toFixed(3)}s
        </div>
      )}
    </div>
  )
}

