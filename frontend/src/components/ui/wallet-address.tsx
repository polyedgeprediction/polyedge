import { useState } from 'react'
import { cn } from '@/lib/utils'
import { formatAddress } from '@/lib/formatters'
import { Copy, ExternalLink, Check } from 'lucide-react'

interface WalletAddressProps {
  address: string
  showCopy?: boolean
  showLink?: boolean
  className?: string
}

export function WalletAddress({
  address,
  showCopy = true,
  showLink = false,
  className,
}: WalletAddressProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(address)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span className="font-mono text-sm text-primary">
        {formatAddress(address)}
      </span>
      {showCopy && (
        <button
          onClick={handleCopy}
          className="text-muted hover:text-secondary transition-colors"
          title={copied ? "Copied!" : "Copy address"}
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-profit" />
          ) : (
            <Copy className="w-3.5 h-3.5" />
          )}
        </button>
      )}
      {showLink && (
        <a
          href={`https://polygonscan.com/address/${address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-muted hover:text-secondary transition-colors"
        >
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      )}
    </span>
  )
}

