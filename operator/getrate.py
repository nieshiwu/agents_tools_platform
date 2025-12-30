"""汇率查询工具"""

import httpx
from langchain_core.tools import tool


@tool
def get_exchange_rate(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    currency_date: str = "latest"
) -> dict:
    """查询货币汇率（基于欧洲央行数据）。

    Args:
        currency_from: 源货币代码（例如 "USD", "EUR", "GBP", "JPY"）。
        currency_to: 目标货币代码（例如 "EUR", "GBP", "JPY"）。
        currency_date: 汇率日期，格式为 "YYYY-MM-DD" 或 "latest"（最新汇率）。
    
    注意：该 API 基于欧洲央行数据，支持的货币包括：
    AUD, BGN, BRL, CAD, CHF, CNY, CZK, DKK, EUR, GBP, HKD, HUF, IDR, ILS, 
    INR, ISK, JPY, KRW, MXN, MYR, NOK, NZD, PHP, PLN, RON, SEK, SGD, THB, 
    TRY, USD, ZAR（不保证所有货币对都可用）。

    Returns:
        包含汇率查询结果的字典：
        - success: 是否成功
        - currency_from: 源货币
        - currency_to: 目标货币
        - rate: 汇率
        - date: 汇率日期
        - message: 状态信息
    """
    if not currency_from or not currency_to:
        return {
            "success": False,
            "currency_from": currency_from,
            "currency_to": currency_to,
            "rate": None,
            "date": None,
            "message": "错误：请提供有效的货币代码"
        }

    try:
        response = httpx.get(
            f"https://api.frankfurter.app/{currency_date}",
            params={"from": currency_from, "to": currency_to},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        if "rates" not in data:
            return {
                "success": False,
                "currency_from": currency_from,
                "currency_to": currency_to,
                "rate": None,
                "date": None,
                "message": "错误：API 返回格式无效"
            }

        rate = data["rates"].get(currency_to)
        return {
            "success": True,
            "currency_from": currency_from,
            "currency_to": currency_to,
            "rate": rate,
            "date": data.get("date"),
            "message": f"1 {currency_from} = {rate} {currency_to}"
        }

    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "currency_from": currency_from,
            "currency_to": currency_to,
            "rate": None,
            "date": None,
            "message": f"错误：API 请求失败 - HTTP {e.response.status_code}"
        }
    except httpx.RequestError as e:
        return {
            "success": False,
            "currency_from": currency_from,
            "currency_to": currency_to,
            "rate": None,
            "date": None,
            "message": f"错误：网络请求失败 - {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "currency_from": currency_from,
            "currency_to": currency_to,
            "rate": None,
            "date": None,
            "message": f"错误：{str(e)}"
        }


if __name__ == "__main__":
    # 测试
    result = get_exchange_rate.invoke({
        "currency_from": "USD",
        "currency_to": "CNY",
        "currency_date": "latest"
    })
    print(result)
