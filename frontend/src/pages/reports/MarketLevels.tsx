import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { RefreshCw, AlertCircle, ArrowLeft, Users, DollarSign, TrendingUp } from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrencyCompact } from '@/lib/formatters'
import { reports } from '@/lib/api'
import type { MarketLevelsResponse, MarketLevelsOutcome } from '@/types'

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

export default function MarketLevels() {
  const { marketId } = useParams<{ marketId: string }>()
  const navigate = useNavigate()

  // State
  const [data, setData] = useState<MarketLevelsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!marketId) {
      setError('Market ID is required')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await reports.marketLevels(parseInt(marketId))
      if (response.success) {
        setData(response)
        setError(null)
      } else {
        setError(response.errorMessage || 'Failed to load market levels')
        setData(null)
      }
    } catch (err) {
      let errorMessage = 'Failed to fetch data'
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        errorMessage = 'Failed to fetch - Server may be offline'
      } else if (err instanceof Error) {
        errorMessage = err.message
      }
      console.error('MarketLevels fetch error:', err)
      setError(errorMessage)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [marketId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Set document title
  useEffect(() => {
    document.title = data?.market?.question 
      ? `Levels: ${data.market.question.slice(0, 50)}...` 
      : 'Market Levels'
    return () => {
      document.title = 'polyedge'
    }
  }, [data?.market?.question])

  // Filter outcomes to only those with investment
  const outcomesWithInvestment = useMemo(() => {
    if (!data?.outcomes) return []
    return data.outcomes.filter(o => o.totalAmountInvested > 0)
  }, [data?.outcomes])

  // Transform data for each outcome - separate charts
  const outcomeChartData = useMemo(() => {
    if (!outcomesWithInvestment || outcomesWithInvestment.length === 0) return []

    return outcomesWithInvestment.map((outcome: MarketLevelsOutcome) => {
      return {
        outcome: outcome.outcome,
        data: outcome.levels.map(level => ({
          rangeLabel: level.rangeLabel,
          totalAmountInvested: level.totalAmountInvested,
        }))
      }
    })
  }, [outcomesWithInvestment])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/app/reports/smartmoney/concentration')}
            className="h-8 px-2"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <div>
            <h1 className="text-xl font-semibold text-primary">
              Buying Levels Distribution
            </h1>
            <p className="text-sm text-muted mt-0.5">
              Average entry price distribution of open positions
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchData}
          disabled={loading}
          className="h-8"
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </>
          )}
        </Button>
      </div>

      {/* Error State */}
      {error && !loading && (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-full bg-loss-bg flex items-center justify-center mb-4">
                <AlertCircle className="w-8 h-8 text-loss" />
              </div>
              <h3 className="text-lg font-medium text-primary mb-2">
                {error.includes('not found') ? 'Market Not Found' : 'Error Loading Data'}
              </h3>
              <p className="text-sm text-muted mb-4 max-w-md">
                {error}
              </p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => navigate('/app/reports/smartmoney/concentration')}>
                  Go Back
                </Button>
                <Button onClick={fetchData}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Try Again
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {loading && !error && (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center justify-center text-center">
              <RefreshCw className="w-8 h-8 animate-spin text-muted mb-4" />
              <p className="text-sm text-muted">Loading market levels...</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Data Display */}
      {!loading && !error && data && (
        <>
          {/* Market Info Card */}
          <Card>
            <CardContent className="py-4">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h2 className="text-lg font-medium text-primary truncate">
                    {data.market.question}
                  </h2>
                  <p className="text-xs text-muted mt-1 font-mono">
                    Market ID: {data.market.marketId}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-surface border border-border-subtle rounded-lg p-4">
              <div className="flex items-center gap-2 text-muted mb-1">
                <Users className="w-4 h-4" />
                <span className="text-sm">Total Wallets</span>
              </div>
              <div className="text-2xl font-semibold font-mono tabular-nums text-primary">
                {data.summary.totalWalletCount}
              </div>
            </div>
            <div className="bg-surface border border-border-subtle rounded-lg p-4">
              <div className="flex items-center gap-2 text-muted mb-1">
                <TrendingUp className="w-4 h-4" />
                <span className="text-sm">Total Positions</span>
              </div>
              <div className="text-2xl font-semibold font-mono tabular-nums text-primary">
                {data.summary.totalPositionCount}
              </div>
            </div>
            <div className="bg-surface border border-border-subtle rounded-lg p-4">
              <div className="flex items-center gap-2 text-muted mb-1">
                <DollarSign className="w-4 h-4" />
                <span className="text-sm">Total Invested</span>
              </div>
              <div className="text-2xl font-semibold font-mono tabular-nums text-primary">
                {formatCurrencyCompact(data.summary.totalAmountInvested)}
              </div>
            </div>
          </div>

          {/* Charts - One per outcome with investment */}
          {outcomeChartData.length > 0 ? (
            <div className={`grid gap-4 ${outcomeChartData.length === 1 ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-2'}`}>
              {outcomeChartData.map((outcomeChart) => {
                const outcome = outcomesWithInvestment.find(o => o.outcome === outcomeChart.outcome)!
                return (
                  <Card key={outcomeChart.outcome}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle 
                          className="text-lg"
                          style={{ color: getOutcomeColor(outcomeChart.outcome) }}
                        >
                          {outcomeChart.outcome}
                        </CardTitle>
                        <div className="flex items-center gap-4 text-xs text-muted">
                          <span>{outcome.totalWalletCount} wallets</span>
                          <span>{outcome.totalPositionCount} positions</span>
                          <span className="font-mono tabular-nums">
                            {formatCurrencyCompact(outcome.totalAmountInvested)}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-muted mt-1">
                        Investment distribution across price ranges
                      </p>
                    </CardHeader>
                    <CardContent>
                      <div className="h-[350px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={outcomeChart.data}
                            margin={{ top: 20, right: 20, left: 20, bottom: 20 }}
                          >
                            <XAxis
                              dataKey="rangeLabel"
                              stroke="#71717a"
                              fontSize={11}
                              tickLine={false}
                              axisLine={false}
                              tick={{ fill: '#a1a1aa' }}
                            />
                            <YAxis
                              stroke="#71717a"
                              fontSize={11}
                              tickLine={false}
                              axisLine={false}
                              tickFormatter={formatYAxis}
                              tick={{ fill: '#a1a1aa' }}
                              width={60}
                            />
                            <Tooltip
                              content={({ active, payload, label }) => {
                                if (!active || !payload || payload.length === 0) return null
                                return (
                                  <div className="bg-surface border border-border-subtle rounded-lg p-3 shadow-lg">
                                    <p className="text-xs text-muted mb-2">Price Range: {label}</p>
                                    <div className="space-y-1">
                                      <div className="flex items-center justify-between gap-4">
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
                                  </div>
                                )
                              }}
                            />
                            <Bar
                              dataKey="totalAmountInvested"
                              fill={getOutcomeColor(outcomeChart.outcome)}
                              radius={[4, 4, 0, 0]}
                              maxBarSize={50}
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
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          ) : (
            <Card>
              <CardContent className="py-12">
                <div className="flex flex-col items-center justify-center text-center">
                  <p className="text-muted">No position data available</p>
                </div>
              </CardContent>
            </Card>
          )}


          {/* Execution time footer */}
          <div className="text-xs text-muted text-right">
            Query executed in {data.executionTimeSeconds.toFixed(3)}s
          </div>
        </>
      )}
    </div>
  )
}

