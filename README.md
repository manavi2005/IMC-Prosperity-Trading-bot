# IMC-Prosperity-Trading-bot

## Team name: Arbitragia 
Placed in the Top 500 amongst 15k particpants. Here's a break down of what we did.

## Algorithm

### Round –1 Strategy

In Round –1, the bot uses Python’s standard libraries (`math`, `jsonpickle`, optional `matplotlib`) alongside the `datamodel` API to implement three market‐making engines. First, Resin anchors every quote at a fixed fair value of 10 000, buying when the ask falls below and selling when the bid rises above, then flattening any leftover position at midpoint and posting passive one‐tick‐inside orders. Second, Kelp computes a dynamic fair value as the volume‐weighted average of best bids and asks, takes liquidity when prices stray beyond a threshold, and otherwise posts passive quotes inside the spread while tracking VWAP and volume history. Third, Squid Ink builds on the VWAP fair value by maintaining a rolling window of recent fair values, computing a z‐score to gauge short‐term mispricing, and selecting the single best buy and sell price each tick via a utility that balances expected profit (minus slippage and transaction cost), execution probability, inventory‐risk penalty, and a mean‐reversion bonus. A shared “clear position” helper ensures any residual inventory is neutralized at the fair midpoint.

### Round 2 Strategy

Round 2 introduces a pure‐Python conversion arbitrage leg on top of the existing market‐making engines. Using the same technical stack plus linear‐programming logic, it calculates mid‐prices (or synthetic fair values) for Croissant, Jam, Djembe and two composite baskets (6×Croissant + 3×Jam + 1×Djembe; 4×Croissant + 2×Jam). An “advantage” vector of mispricings drives full long or short positions at each product’s limit when mispricing exists. The LP solution is then decomposed into executable orders by comparing current positions to targets and placing trades at the best available book prices, capturing conversion profits in real time alongside Resin, Kelp, and Squid Ink strategies.

### Round 3 Strategy

In Round 3, we extend our unified framework with option pricing and an experimental manual module. We add Volcanic Rock Vouchers treated as European call options priced using a custom Black–Scholes implementation, automatically buying when market asks are below theoretical prices and selling when bids exceed them, all configurable by strike, tenor, volatility, and position limit. The LP conversion arbitrage persists for baskets and components, and a lightweight Flippers module logs second‐best bid history for future manual strategies. Each `run()` method orchestrates all engines, enforces per‐symbol position limits, invokes the common clear‐position helper, and serializes time‐series metrics for offline analysis, producing a cohesive, ever‐more powerful toolkit for market making, statistical arbitrage, and conversion profits.

### Round 4 Strategy

In Round 4, we extend our unified Trader class to support the Magnificent Macarons conversion game. By calculating implied bid and ask levels from ConversionObservations—including export/import tariffs, transport fees, and storage costs—the bot executes a two-leg arbitrage: an aggressive “take” leg that crosses favorable market quotes when they beat implied edges, followed by a “make” leg that posts passive quotes just inside implied prices. Positions are then unwound via conversion transactions capped per tick. This new module seamlessly reuses the shared clear-position helper and coexists alongside Resin, Kelp, Squid Ink, and basket strategies, delivering a fully modular, multi-asset arbitrage framework.

### Round 5 Strategy

In Round 5, we refactor and streamline the entire codebase for clarity and maintainability without altering any core quantitative logic. Common helpers for mid-price, VWAP, LP conversion, and Black–Scholes option pricing are consolidated; price rounding is standardized; order-generation loops are unified across all products; and time-series metrics are logged consistently. These DRY-driven improvements embrace Python best practices and yield a more readable, modular, and extensible trading bot framework.
