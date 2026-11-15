import akshare as ak
import pandas as pd
from sqlalchemy import create_engine
from config import DB_CONFIG

# 组装 SQLAlchemy 连接字符串
DB_URL = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

def extract_and_rename(df, mappings, date_col='报告日'):
    rename_dict = {}
    for target_name, keyword in mappings.items():
        for col in df.columns:
            if keyword in str(col) and '同比' not in str(col) and '减' not in str(col):
                rename_dict[col] = target_name
                break
    if not all(k in rename_dict.values() for k in mappings.keys()):
        return None
    df_clean = df[list(rename_dict.keys()) + [date_col]].copy()
    df_clean.rename(columns=rename_dict, inplace=True)
    df_clean.rename(columns={date_col: '报告期'}, inplace=True)
    return df_clean

try:
    print("开始抓取最新 A 股数据...")
    df_p = extract_and_rename(ak.stock_financial_report_sina(stock="sh600519", symbol="利润表"), {'营业总收入': '营业总收入', '归母净利润': '归属于母公司所有者的净利润'})
    df_b = extract_and_rename(ak.stock_financial_report_sina(stock="sh600519", symbol="资产负债表"), {'总资产': '资产总计', '总负债': '负债合计'})
    df_c = extract_and_rename(ak.stock_financial_report_sina(stock="sh600519", symbol="现金流量表"), {'经营现金流': '经营活动产生的现金流量净额'})

    if df_p is not None and df_b is not None and df_c is not None:
        df_merged = pd.merge(df_p, df_b, on='报告期', how='inner')
        df_merged = pd.merge(df_merged, df_c, on='报告期', how='inner')
        df_merged['报告期'] = pd.to_datetime(df_merged['报告期'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        df_merged = df_merged.sort_values('报告期', ascending=False).dropna(subset=['营业总收入'])

        engine = create_engine(DB_URL)
        # 存入数据库
        df_merged.to_sql('financial_data', engine, if_exists='replace', index=False)
        print(f"✅ 成功！共 {len(df_merged)} 期数据已入库！")
except Exception as e:
    print(f"❌ 拉取过程中发生错误: {e}")