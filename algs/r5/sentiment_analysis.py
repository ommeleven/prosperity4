
from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wl, wlexpr
import numpy as np
import cvxpy as cp


sentiments = {
    'Obsidian': '--',
    'Pyroflex': '--',
    'Thermalite': '++++',
    'Ashes': '-',
    'cake': '--',
    'Magma': '+++',
    'Scoria': '+',
    'Volcanic': '+',
    'Sulfur': '+++'
}

returns = {
    '+': 0.05,
    '++': 0.15,
    '+++': 0.25,
    '++++': 0.35,
    '-': -0.05,
    '--': -0.1,
    '---': -0.4,
    '----': -0.6
}

products = list(sentiments.keys())
print("Products:", products)

rets = np.array([returns[sentiments[products[i-1]]] for i in range(1,10)])
pi = cp.Variable(9)
objective = cp.Minimize(100 * cp.sum_squares(pi) - 10000 * rets.T @ pi)
constraints = [cp.norm(pi, 1) <= 100]
prob = cp.Problem(objective, constraints)

prob.solve()
print('Optimal allocation without integer constraints:')
for i in range(9):
    print("Position in ", products[i], ': ', f"{pi.value[i]:,.2f}", '%', sep='')

#building blocks for the Mathematica command
s1 = ' + '.join(['('+str(returns[sentiments[products[i-1]]])+')*p'+str(i)+'*10000-100*(p'+str(i)+')^2' for i in range(1,10)])
s2 = ' + '.join(['Abs[p'+str(i)+']' for i in range(1,10)]) + '<=100,'
s3 = ', '.join(['Element[p'+str(i)+', Integers]' for i in range(1,10)])
s4 = ', '.join(['p'+str(i) for i in range(1,10)])

print('NMaximize[{'+s1+','+s2+s3+'}, {'+s4+'}]')


with WolframLanguageSession() as session:
    val_max, sol = session.evaluate(wlexpr('NMaximize[{'+s1+','+s2+s3+'}, {'+s4+'}]'))

print("Maximum profit achievable:", val_max)

print("Percentage of capital used: ", sum([abs(el[1]) for el in sol]), '%', sep='')

for i in range(9):
    print("Position in ", products[i], ': ', sol[i][1], '%', sep='')
