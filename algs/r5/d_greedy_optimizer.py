import heapq

products = ['Obsidian cutlery','Pyrofiex cells','Thermalite core','Lava cake','Magma ink',
            'Scoria paste','Ashes of the Phoenix','Volcanic incense','Sulfur reactor']
# Replace these with your actual expected returns (as fractions, e.g., 0.15 for +15%)
expected_returns = [ -0.20, -0.10, 0.25, -0.05, 0.15, 0.05, -0.30, 0.08, 0.20 ]  # example only
# ^ YOU MUST UPDATE THIS WITH REAL NEWS SENTIMENT

budget_total = 100
allow_short = True

alloc = {p: 0 for p in products}
heap = []

for i, p in enumerate(products):
    r = expected_returns[i]
    if allow_short:
        if r > 0:
            gain = 10000 * r - 100
            if gain > 0:
                heapq.heappush(heap, (-gain, i, +1))
        elif r < 0:
            gain = 10000 * abs(r) - 100
            if gain > 0:
                heapq.heappush(heap, (-gain, i, -1))
    else:
        if r > 0:
            gain = 10000 * r - 100
            if gain > 0:
                heapq.heappush(heap, (-gain, i, +1))

total_abs = 0
while total_abs < budget_total and heap:
    neg_gain, i, direction = heapq.heappop(heap)
    gain = -neg_gain
    if gain <= 0:
        break
    p = products[i]
    alloc[p] += direction
    total_abs += 1
    k = abs(alloc[p])
    r = expected_returns[i]
    next_gain = 10000 * abs(r) - 100 * (2*k + 1)
    if next_gain > 0:
        heapq.heappush(heap, (-next_gain, i, direction))

print("Optimal allocation (greedy, budget=100%):")
for p in products:
    print(f"{p}: {alloc[p]}%")
print(f"\nTotal absolute used: {total_abs}%")