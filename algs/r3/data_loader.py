import pandas as pd

def load_day(path):
    df = pd.read_csv(path, sep=";")
    return df

def load_all():
    files = [
        "/Users/HP/src/prosperity4/algs/r3/prices_round_3_day_0.csv",
        "/Users/HP/src/prosperity4/algs/r3/prices_round_3_day_1.csv",
        "/Users/HP/src/prosperity4/algs/r3/prices_round_3_day_2.csv"
    ]

    dfs = [load_day(f) for f in files]
    return pd.concat(dfs, ignore_index=True)


if __name__ == "__main__":
    df = load_all()
    print(df.head())