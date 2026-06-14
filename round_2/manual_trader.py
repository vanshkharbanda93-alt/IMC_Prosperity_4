import numpy as np
from scipy.optimize import minimize

def eval_speed(z, expected_competitor_avg=33.0, competitiveness=0.15):
    """
    Evaluates the Speed multiplier using a logistic probability curve.
    
    :param z: Your investment in the Speed pillar (0-100)
    :param expected_competitor_avg: Where you think the median player will invest.
    :param competitiveness: How sharply the multiplier changes around the average.
    """
    min_mult = 0.1
    max_mult = 0.9
    
    # Calculate the sigmoid. 
    # We clip the exponent to prevent math overflow errors in SciPy
    exponent = np.clip(-competitiveness * (z - expected_competitor_avg), -100, 100)
    sigmoid_curve = 1 / (1 + np.exp(exponent))
    
    # Scale the 0-1 sigmoid to fit between our 0.1 and 0.9 boundaries
    return min_mult + (max_mult - min_mult) * sigmoid_curve

def eval_speed_smart(z, zero_bidder_fraction=0.20, pack_avg=33.3, speed_climb=0.2):
    """
    Evaluates Speed assuming a fraction of players bid exactly 0.
    
    :param z: Your investment in the Speed pillar (0-100)
    :param zero_bidder_fraction: Estimated % of players who invest 0 (e.g., 0.20 = 20%)
    :param pack_avg: Estimated median investment of the REMAINING players.
    """
    # The total multiplier range 0.8 (from 0.1 to 0.9)
    total_delta = 0.8
    jump_reward_max = total_delta * zero_bidder_fraction
    
    # exponential climb of bet made by users
    zero_jump = jump_reward_max * (1 - np.exp(-speed_climb * z))
    pack_reward_max = total_delta * (1 - zero_bidder_fraction)
    
    # Standard sigmoid for the main competition
    competitiveness = 0.2
    exponent = np.clip(-competitiveness * (z - pack_avg), -100, 100)
    pack_battle = pack_reward_max * (1 / (1 + np.exp(exponent)))
    return 0.1 + zero_jump + pack_battle


# Your updated Objective Function
def PnL(x_vars):
    x = x_vars[0]  # Research
    y = x_vars[1]  # Scale
    z = x_vars[2]  # Speed
    
    # 1. Evaluate Pillars
    research = 200000 * (np.log(1 + x) / np.log(101))
    scale = 7 * (y / 100)
    
    # speed = eval_speed(z, expected_competitor_avg=50.0, competitiveness=0.2)
    speed = eval_speed_smart(z, zero_bidder_fraction=0.1, pack_avg=57.0) # Using smart predictor that assumes that at least few users bet 0%
    
    # 2. Calculate PnL
    gross_pnl = research * scale * speed
    budget_used = (x + y + z) * 500
    
    # Minimize negative PnL
    return -1 * (gross_pnl - budget_used)

# Constraint: x + y + z <= 100
def constr(x_vars):
    return 100 - x_vars[0] - x_vars[1] - x_vars[2]

# Run the optimization
my_constraints = {'type': 'ineq', 'fun': constr}
bounds = ((0, 100), (0, 100), (0, 100))

result = minimize(
    PnL, 
    x0=np.array([33, 33, 34]), 
    method='SLSQP', 
    bounds=bounds, 
    constraints=my_constraints
)

print(f"Optimal Allocation - Research: {result.x[0]:.2f}%, Scale: {result.x[1]:.2f}%, Speed: {result.x[2]:.2f}%")
print(f"Projected Max PnL: {-result.fun:,.2f}")

##### integer, maybe smarter ######
import numpy as np
from scipy.stats import norm

def build_opponent_distribution():
    dist = np.zeros(101)
    
    # ---------------------------------------------------------
    # WEIGHTS: with the "High Rollers" (up to 80)
    # ---------------------------------------------------------
    weight_quitters = 0.07      # 3% bid 0
    weight_lazy = 0.10          # 10% bid 33 or 34
    weight_schelling = 0.10     # 10% bid 10, 20, 25, 50
    weight_sunk_cost = 0.40     # 42% optimize and hit good avergages (gasussian centered around 40)
    weight_high_rollers = 0.30  # 35% panic and bid anywhere from 50 to 80
    weight_whales = 0.03        # 3% go absolute all-in (81 to 96)
    # ---------------------------------------------------------
    assert(weight_quitters+weight_lazy+weight_schelling+weight_sunk_cost+weight_high_rollers+weight_whales==1)
    # 1. Quitters
    dist[0] += weight_quitters
    
    # 2. Lazy Splitters
    dist[33] += weight_lazy / 2
    dist[34] += weight_lazy / 2
    
    # 3. Schelling Point Guessers
    schelling_points = [10, 20, 25, 50, 66]
    for p in schelling_points:
        dist[p] += weight_schelling / len(schelling_points)
        
    # 4. Sunk Cost Optimizers (Normal curve around 28)
    sunk_cost_curve = norm.pdf(np.arange(101), loc=40, scale=3)
    dist += (sunk_cost_curve / np.sum(sunk_cost_curve)) * weight_sunk_cost
    
    # 5. The High Rollers (Uniform spread from 50 to 80)
    high_roller_bids = np.arange(40, 81)
    for p in high_roller_bids:
        dist[p] += weight_high_rollers / len(high_roller_bids)
        
    # 6. The Whales (Uniform spread from 81 to 100)
    whale_bids = np.arange(81, 96)
    for p in whale_bids:
        dist[p] += weight_whales / len(whale_bids)

    return dist / np.sum(dist)

def get_expected_multiplier(z, opp_dist):
    strictly_beaten = np.sum(opp_dist[:z]) if z > 0 else 0
    tied = opp_dist[z]
    percentile = strictly_beaten + (0.5 * tied)
    return 0.1 + (0.8 * percentile)

def calculate_gross_pnl(x, y, speed_mult):
    research = 200000 * (np.log(1 + x) / np.log(101))
    scale = 7 * (y / 100)
    return research * scale * speed_mult

def optimize_allocation():
    opp_dist = build_opponent_distribution()
    best_pnl = -np.inf
    best_allocation = (0, 0, 0)
    
    for x in range(101):
        for y in range(101 - x):
            z = 100 - x - y
            
            expected_mult = get_expected_multiplier(z, opp_dist)
            gross_pnl = calculate_gross_pnl(x, y, expected_mult)
            net_pnl = gross_pnl - ((x + y + z) * 500)
            
            if net_pnl > best_pnl:
                best_pnl = net_pnl
                best_allocation = (x, y, z)
                best_mult = expected_mult
                
    return best_allocation, best_pnl, best_mult

# Run it
(opt_x, opt_y, opt_z), max_pnl, exp_mult = optimize_allocation()

print(f"Optimal Allocation against updated population:")
print(f"Research: {opt_x}%, Scale: {opt_y}%, Speed: {opt_z}%")
print(f"Research: {200000 * (np.log(1 + opt_x) / np.log(101))}, Scale: {7 * (opt_y / 100)}, Speed: {opt_z}%")

print(f"Expected Multiplier Secured: {exp_mult:.3f}")
print(f"Expected Net PnL: {max_pnl:,.2f}")