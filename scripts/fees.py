# ==============================================================
# fees.py — Centralized fee configuration for all exchanges
# ==============================================================

# --------------------------------------------------------------
# 1. Spot trading fees (taker & maker) per exchange
# --------------------------------------------------------------
# All values are decimal percentages, e.g. 0.001 = 0.1%

TRADING_FEES_TAKER = {
    # Binance Spot — Regular user, no BNB discount
    # Maker/Taker = 0.100% / 0.100%
    "binance": 0.0010,

    # Kraken Pro Spot — lowest tier
    # Maker/Taker = 0.25% / 0.40%
    # Arbitrage traditionally uses taker fees:
    "kraken":  0.0040,

    # KuCoin Spot — LV0
    # Maker/Taker = 0.100% / 0.100%
    "kucoin":  0.0010,

    # Bybit Spot — default retail user
    # Maker/Taker = 0.10% / 0.10%
    "bybit":   0.0010,
}

TRADING_FEES_MAKER = {
    "binance": 0.0010,  # 0.10%
    "kraken":  0.0025,  # 0.25%
    "kucoin":  0.0010,  # 0.10%
    "bybit":   0.0010,  # 0.10%
}

# --------------------------------------------------------------
# 2. Withdrawal fees (cross-exchange transfer costs)
# --------------------------------------------------------------
# Structure:
# WITHDRAWAL_FEES[exchange][symbol] = {
#     "CHAIN": fee_in_token_units,
#     ...
# }
#
# Example:
#  - WITHDRAWAL_FEES["binance"]["USDT"]["TRX"]  = 0.8
#    means withdrawing USDT via TRX network on Binance costs 0.8 USDT.
# --------------------------------------------------------------

WITHDRAWAL_FEES = {
    # ----------------------------------------------------------
    # BINANCE — stablecoins + a few majors (from Binance fee page)
    # ----------------------------------------------------------
    "binance": {
        # ---------- USDT ----------
        "USDT": {
            "TRX":  0.8,   # Tether USD (Tron)     — 0.8 USDT
            "SOL":  0.25,  # Tether USD (Solana)   — 0.25 USDT
            "ETH":  0.75,  # Tether USD (Ethereum) — 0.75 USDT
            "BNB":  0.3,   # Tether USD (BEP20)    — 0.3 USDT
        },

        # ---------- USDC ----------
        "USDC": {
            "ETH":  0.8,   # USDC (Ethereum)
            "TRX":  0.8,   # USDC (Tron)
            "SOL":  0.2,   # USDC (Solana)
            "BNB":  0.25,  # USDC (BEP20)
        },

        # ---------- DAI ----------
        "DAI": {
            "ETH":  0.8,   # DAI (Ethereum)
            "BNB":  0.1,   # DAI (BEP20)
        },

        # ---------- majors (optional, handy for routing) ----------
        "BTC": {
            "BTC": 0.0002,   # Bitcoin network
            "TRX": 0.00001,  # e.g. wrapped variant on Tron
        },
        "ETH": {
            "ETH": 0.0012,
            "ARB": 0.0004,   # Arbitrum One
        },
    },

    # ----------------------------------------------------------
    # KRAKEN — stablecoins we care about
    # (values from the big Kraken list you pasted)
    # ----------------------------------------------------------
    "kraken": {
        # ---------- USDT ----------
        "USDT": {
            "APT":  0.30,  # Tether USD (Aptos)      — 0.30 USDT
            "ARB":  2.0,   # Tether USD (Arbitrum)   — 2 USDT
            "AVAX": 1.0,   # Tether USD (Avalanche)  — 1 USDT
            "ETH":  0.62,  # Tether USD (Ethereum)   — 0.62 USDT
            "FLR":  2.0,   # Tether USD (Flare)      — 2 USDT
            "INK":  0.0,   # Tether USD (Ink)        — 0 USDT
            "OP":   2.0,   # Tether USD (Optimism)   — 2 USDT
            "PLASMA": 1.0, # Tether USD (Plasma)     — 1 USDT
            "POLYGON": 1.0,# Tether USD (Polygon)    — 1 USDT
            "SOL":  0.84,  # Tether USD (Solana)     — 0.84 USDT
            "TON":  2.0,   # Tether USD (TON)        — 2 USDT
            "TRX":  4.0,   # Tether USD (Tron)       — 4 USDT
            "UNI":  2.0,   # Tether USD (Unichain)   — 2 USDT
        },

        # ---------- USDC ----------
        "USDC": {
            "ARB":  2.0,   # USDC (Arbitrum One)
            "AVAX": 1.0,   # USDC (Avalanche)
            "BASE": 0.5,   # USDC (Base)
            "ETH":  0.63,  # USDC (Ethereum)
            "INK":  0.0,   # USDC (Ink)
            "NOBLE":1.0,   # USDC (Noble)
            "OP":   2.0,   # USDC (Optimism)
            "POLYGON":1.0, # USDC (Polygon)
            "SOL":  0.84,  # USDC (Solana)
            "SONIC":1.0,   # USDC (Sonic)
            "SUI":  2.0,   # USDC (Sui)
            "XDC":  0.0,   # USDC (XDC Network) — free, fee in XDC
        },

        # ---------- DAI ----------
        "DAI": {
            "ARB":  2.0,   # Dai (Arbitrum One)
            "ETH":  0.52,  # Dai (Ethereum)
            "MATIC":1.0,   # Dai (Polygon)
        },

        # ---------- majors ----------
        "BTC": {
            "BTC": 0.000015,  # Bitcoin
            "LIGHTNING": 0.0  # BTC Lightning
        },
        "ETH": {
            "ETH": 0.000100,
            "ARB": 0.00015,
            "OP":  0.00015,
        },
    },

    # ----------------------------------------------------------
    # KUCOIN — from WithdrawalFees.com snapshot you pasted
    # (we only plug *our* stablecoins)
    # ----------------------------------------------------------
    "kucoin": {
        # ---------- USDT ----------
        "USDT": {
            "TON":   0.0,   # USDT (TON)         — Free
            "PLASMA":0.4,   # USDT (Plasma)      — 0.4 USDT
            "NEAR":  0.5,   # USDT (Near)        — 0.5 USDT
            "KCC":   0.5,   # USDT (KuCoin Chain)— 0.5 USDT
            "APT":   0.5,   # USDT (Aptos)       — 0.5 USDT
            "POLYGON":0.8,  # USDT (Polygon POS) — 0.8 USDT
            "DOT":   1.0,   # USDT (Polkadot)    — 1 USDT
            "AVAX":  1.0,   # USDT (Avalanche)   — 1 USDT
            "ARB":   1.0,   # USDT (Arbitrum)    — 1 USDT
            "OP":    1.0,   # USDT (Optimism)    — 1 USDT
            "BNB":   1.0,   # USDT (BNB Smart)   — 1 USDT
            "XTZ":   1.0,   # USDT (Tezos)       — 1 USDT
            "SOL":   1.5,   # USDT (Solana)      — 1.5 USDT
            "TRX":   1.5,   # USDT (Tron)        — 1.5 USDT
            "ETH":   5.5,   # USDT (Ethereum)    — 5.5 USDT
        },

        # ---------- USDC ----------
        "USDC": {
            "XDC":   0.0,   # USDC (XDC)         — Free
            "MONAD": 0.1,   # USDC (Monad)       — 0.1 USDC
            "SONIC": 0.21,  # USDC (Sonic)       — 0.21 USDC
            "KCC":   0.5,   # USDC (KCC)         — 0.5 USDC
            "BASE":  0.5,   # USDC (Base)        — 0.5 USDC
            "SUI":   0.5,   # USDC (Sui)         — 0.5 USDC
            "NEAR":  0.5,   # USDC (Near)        — 0.5 USDC
            "ARB":   1.0,   # USDC (Arbitrum)    — 1 USDC
            "ALGO":  1.0,   # USDC (Algorand)    — 1 USDC
            "SOL":   1.0,   # USDC (Solana)      — 1 USDC
            "DOT":   1.0,   # USDC (Polkadot)    — 1 USDC
            "AVAX":  1.0,   # USDC (Avalanche)   — 1 USDC
            "NOBLE": 1.0,   # USDC (Noble)       — 1 USDC
            "OP":    1.0,   # USDC (Optimism)    — 1 USDC
            "ETH":   5.5,   # USDC (Ethereum)    — 5.5 USDC
            "HBAR":  34.95, # USDC (Hedera)      — 35 USDC
        },

        # ---------- USDT/USDC majors & routing coins ----------
        "BTC": {
            "BTC": 0.00009,
            "ARB": 0.0001,
            "BSC": 0.000004,
        },
        "ETH": {
            "ETH": 0.0015,
            "ARB": 0.0002,
            "OP":  0.0002,
        },
        "XRP": {
            "XRP": 0.3,
        },
    },

    # ----------------------------------------------------------
    # BYBIT — from WithdrawalFees.com snapshot + manual USDT
    # ----------------------------------------------------------
    "bybit": {
        # ---------- USDT ----------
        "USDT": {
            "TON": 1.0,   # USDT (TON network)
            "TRX": 3.5,   # USDT (TRC-20)
            "ETH": 6.0,   # USDT (ERC-20), midpoint 4–8
        },

        # ---------- USDC ----------
        "USDC": {
            "SUI":   0.0,   # USDC (Sui)           — Free
            "MANTLE":0.0,   # USDC (Mantle)        — Free
            "XDC":   0.0,   # USDC (XDC Network)   — Free
            "SONIC": 0.05,  # USDC (Sonic)         — 0.05 USDC
            "APT":   0.05,  # USDC (Aptos)         — 0.05 USDC
            "BNB":   0.2,   # USDC (BNB Smart)     — 0.2 USDC
            "BASE":  0.5,   # USDC (Base)          — 0.5 USDC
            "SEI":   0.5,   # USDC (Sei)           — 0.5 USDC
            "HBAR":  0.5,   # USDC (Hedera)        — 0.5 USDC
            "AVAX":  1.0,   # USDC (Avalanche)     — 1 USDC
            "SOL":   1.0,   # USDC (Solana)        — 1 USDC
            "ARB":   1.0,   # USDC (Arbitrum One)  — 1 USDC
            "CODEX": 1.0,   # USDC (Codex)         — 1 USDC
            "MONAD": 1.0,   # USDC (Monad)         — 1 USDC
            "OP":    1.0,   # USDC (Optimism)      — 1 USDC
            "POLYGON":1.0,  # USDC (Polygon POS)   — 1 USDC
            "ETH":   4.99,  # USDC (Ethereum)      — 4.99 USDC
        },

        # ---------- DAI ----------
        "DAI": {
            "BNB": 0.8,   # DAI (BNB Smart Chain) — 0.8 DAI
            "ETH": 4.0,   # DAI (Ethereum)        — 4 DAI
        },
    },
}

# --------------------------------------------------------------
# 3. Helper functions
# --------------------------------------------------------------

def get_taker_fee(exchange: str) -> float | None:
    """Return the taker fee (decimal)."""
    return TRADING_FEES_TAKER.get(exchange)

def get_maker_fee(exchange: str) -> float | None:
    """Return the maker fee (decimal)."""
    return TRADING_FEES_MAKER.get(exchange)
