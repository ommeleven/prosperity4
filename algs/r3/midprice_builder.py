import pandas as pd

def build_mid(df):
    df["mid"] = df["mid_price"]

    clean = df[["timestamp", "product", "mid"]].dropna()
    return clean

def pivot_prices(df):
    return df.pivot(index="timestamp", columns="product", values="mid")

if __name__ == "__main__":
    from data_loader import load_all

    df = load_all()
    mid = build_mid(df)
    print(mid.head())