# Original Round 3 Strategy

## Traded Products

The trader focused on the following products:

```text
HYDROGEL_PACK
VELVETFRUIT_EXTRACT
VEV_5000
VEV_5100
VEV_5200
VEV_5300
```

The strategy did not trade the deepest ITM or farthest OTM vouchers.

## Strategy Overview

The trader had three main components:

1. `HYDROGEL_PACK` passive market making
2. `VELVETFRUIT_EXTRACT` fair-value trading
3. Voucher pricing and trading for `VEV_5000`, `VEV_5100`, `VEV_5200`, and `VEV_5300`

## HYDROGEL_PACK

`HYDROGEL_PACK` was traded with a simple passive market-making strategy around a fixed fair-value estimate.

The main idea was to capture spread while keeping the logic simple and inventory-aware.

## VELVETFRUIT_EXTRACT

For `VELVETFRUIT_EXTRACT`, the fair-value estimate combined three signals: the microprice, a faster EMA, and a slower EMA.

The microprice used the best bid/ask volumes to tilt the fair value toward the heavier side of the order book, making the estimate more responsive to short-term imbalance. The faster EMA helped the fair value adjust when the market started moving, while the slower EMA made it less sensitive to very short-lived price changes.

In practice, this gave us a VFE fair value that was more reactive than a simple moving average, but less noisy than using the raw mid-price or microprice alone. We tried a few different fair-value estimates, and this version performed best on the IMC simulator.

This fair value was used both for direct `VELVETFRUIT_EXTRACT` trading and as the underlying spot input for voucher pricing.

## Voucher Options Overlay

The voucher strategy treated the selected `VEV_*` products as call options on `VELVETFRUIT_EXTRACT` with 5 days left for expiration.

The idea was to compare the vouchers in implied-volatility terms rather than looking at their raw prices directly. Raw option prices are hard to compare across strikes, because a lower-strike voucher will naturally trade at a higher price than a higher-strike voucher. By converting each voucher price into an implied volatility, we could put the different strikes on a more comparable scale. At each timestamp, the strategy used the current voucher mid-prices to estimate implied volatilities, then fitted a IV smile across the traded strikes. This gave a smoothed estimate of what the IV should be for each voucher. That fitted IV was then converted back into a Black-Scholes fair price.

Since the smile was built from only a few strikes, it could easily become noisy or distorted by one bad quote. To avoid reacting too strongly to short-lived noise, the live estimate was balanced slightly with historical IV levels. A trade was only placed when the option looked cheap or expensive in two ways: first relative to the fitted IV smile, and second at the actual bid or ask available in the order book. This helped avoid trading on small model differences that were not large enough to overcome the spread.


## Assumptions

The options strategy depended on a few key assumptions. We assumed that our live fair-value estimate of `VELVETFRUIT_EXTRACT` was accurate enough to price the options.

We also assumed that the voucher IVs should form a reasonably smooth curve across nearby strikes. Because some voucher quotes were noisier than others, tighter-spread options were treated as more reliable inputs. 

## Performance Notes

During testing on the IMC simulator, this strategy produced positive PnL however in the live Round 3 run, the algorithmic performance did not generalize as well as expected. 

