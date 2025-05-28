

""" class DataMerge to Merge data1 and data2 by symbol """
class DataMerge:
    def __init__(self, data1, data2, list_of_symbols):
        def normalize(data):
            normalized = []
            for item in data:
                if "symbol" in {k.lower(): v for k, v in item.items()}:
                    # 保留 symbol 的值原樣，其它 key 全轉小寫
                    new_item = {k.lower(): v for k, v in item.items()}
                    # 找出原始 symbol key 並取出原值
                    for k in item:
                        if k.lower() == "symbol":
                            new_item["symbol"] = item[k]  # 保留大小寫原樣
                            break
                    normalized.append(new_item)
            return normalized

        self.data1 = normalize(data1)
        self.data2 = normalize(data2)
        self.list_of_symbols = list_of_symbols  # 保留大小寫，因為 symbol value 是大寫的
        self.merged_data = []

    def merge_data_by_symbol(self):
        # 用 symbol 的值（大寫）為 key
        data1_map = {item["symbol"]: item for item in self.data1}
        data2_map = {item["symbol"]: item for item in self.data2}

        for symbol in self.list_of_symbols:
            merged = {
                **data1_map.get(symbol, {}),
                **data2_map.get(symbol, {})
            }
            self.merged_data.append(merged)
        return self.merged_data
