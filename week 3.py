import pandas as pd
dolphins = pd.read_csv("dolphins.csv")

observed_counts=pd.crosstab(dolphins["vessels"],dolphins["behav2"])
print("\n Observed Counts:\n" + str(observed_counts))

import scipy.stats as stats
test_result = stats.chi2_contingency(observed_counts,correction=False)
print("\n Expected Frequencies:\n" + str(test_result.expected_freq))

print("\n Test Statistic:\n" + str(test_result.statistic))

print("\n P-Value:\n" + str(test_result.pvalue))

crosstab_prop=pd.crosstab(dolphins["vessels"],dolphins["behav2"],normalize="index")
print("\n Proportions:\n" + str(crosstab_prop))

import matplotlib.pyplot as plt
crosstab_prop.plot(kind='bar',stacked=True)
plt.xlabel("Vessels")
plt.xticks(rotation=0)

plt.ylabel("Proportion")
my_labels=["Forage","Rest/Social/Travel"]
plt.legend(title="Behavior",labels=my_labels)
plt.show()

drinks = pd.read_csv("drinks.csv")
countryList=["USA","China","Italy","Saudi Arabia"]
drinks_smaller = drinks[drinks["country"].isin(countryList)]
drinks_smaller = drinks_smaller.rename(columns={'beer_servings': 'Beer','spirit_servings': 'Spirit','wine_servings': 'Wine'})
drinks_smaller = drinks_smaller.drop(columns=['total_litres_of_pure_alcohol'])
print("\n Reduced Drinks Data:\n" + str(drinks_smaller))

drinks_smaller_long = pd.melt(drinks_smaller,id_vars="country",value_vars=["Beer","Spirit","Wine"])
drinks_smaller_long = drinks_smaller_long.rename(columns={'country': 'Country','variable': 'Type','value': 'Servings'})
print("\n Long Format Drinks Data:\n" + str(drinks_smaller_long))

import seaborn as sns
plt.figure()
sns.catplot(x="Country",y="Servings",hue="Type",data=drinks_smaller_long,kind="bar")
plt.show()
