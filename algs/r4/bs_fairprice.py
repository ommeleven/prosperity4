import math

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def black_scholes(S, K, T, r, sigma, option_type="call"):
    """
    S: spot
    K: strike
    T: time to expiry in years
    r: risk-free rate
    sigma: annualized volatility
    option_type: 'call' or 'put'
    """
    if T <= 0:
        if option_type == "call":
            price = max(S - K, 0.0)
            delta = 1.0 if S > K else 0.0
        else:
            price = max(K - S, 0.0)
            delta = -1.0 if S < K else 0.0
        return {
            "price": price,
            "d1": None,
            "d2": None,
            "delta": delta,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
        }

    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    Nd1 = norm_cdf(d1)
    Nd2 = norm_cdf(d2)
    Nmd1 = norm_cdf(-d1)
    Nmd2 = norm_cdf(-d2)
    pdf_d1 = norm_pdf(d1)

    if option_type == "call":
        price = S * Nd1 - K * math.exp(-r * T) * Nd2
        delta = Nd1
        theta = -(S * pdf_d1 * sigma) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * Nd2
        rho = K * T * math.exp(-r * T) * Nd2
    elif option_type == "put":
        price = K * math.exp(-r * T) * Nmd2 - S * Nmd1
        delta = Nd1 - 1.0
        theta = -(S * pdf_d1 * sigma) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * Nmd2
        rho = -K * T * math.exp(-r * T) * Nmd2
    else:
        raise ValueError("option_type must be 'call' or 'put'")

    gamma = pdf_d1 / (S * sigma * math.sqrt(T))
    vega = S * pdf_d1 * math.sqrt(T)

    return {
        "price": price,
        "d1": d1,
        "d2": d2,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
    }

TRADING_DAYS_PER_YEAR = 252

def weeks_to_years(weeks):
    return (weeks * 5) / TRADING_DAYS_PER_YEAR

def steps_to_years(steps, steps_per_day=4):
    return steps / (TRADING_DAYS_PER_YEAR * steps_per_day)

# Example: 3-week option, S=50, K=50, r=0, vol=251%
res = black_scholes(S=50, K=50, T=weeks_to_years(3), r=0.0, sigma=2.51, option_type="call")
print(res)