import heapq

products = ['Refrigerators','Earrings','Blankets','Sleds','Sculptures','PS6','Serum','Lamps','Chocolate']
sentiments = ['+','++','---','--','++','+++','----','+','-']
returns_map = {'+':0.05, '++':0.15, '+++':0.25, '-':-0.05, '--':-0.1, '---':-0.4, '----':-0.6}
returns = [returns_map[s] for s in sentiments]

budget_total = 100
allow_short = True

alloc = {prod: 0 for prod in products}
heap = []

for i, prod in enumerate(products):
    r = returns[i]
    if allow_short:
        if r > 0:
            gain = 10000 * r - 100
            if gain > 0: heapq.heappush(heap, (-gain, i, +1))
        elif r < 0:
            gain = 10000 * abs(r) - 100
            if gain > 0: heapq.heappush(heap, (-gain, i, -1))
    else:
        if r > 0:
            gain = 10000 * r - 100
            if gain > 0: heapq.heappush(heap, (-gain, i, +1))

total_abs = 0
while total_abs < budget_total and heap:
    neg_gain, i, direction = heapq.heappop(heap)
    gain = -neg_gain
    if gain <= 0: break
    prod = products[i]
    alloc[prod] += direction
    total_abs += 1
    k = abs(alloc[prod])
    r = returns[i]
    next_gain = 10000 * abs(r) - 100 * (2*k + 1)
    if next_gain > 0:
        heapq.heappush(heap, (-next_gain, i, direction))

print("Optimal integer allocation (greedy):")
for prod in products:
    print(f"  {prod}: {alloc[prod]}%")
print(f"\nTotal absolute used: {total_abs}%")