import requests

token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJsb2dpbiI6IlRaUDVCMDBEIiwiZW50aXR5IjoiVFpHIiwianRpIjoiMjUwODE0MzMxNyIsIm5iZiI6MTc0ODU3NDYwNSwiZXhwIjoxNzQ4NjAzNDA1LCJpc3MiOiJUWklEIiwiYXVkIjoiVFpDbGllbnQifQ.ggSzcukiajezcZEYH15hE6ZU6UAtFD3-tdS1_H4-fSYWwSiY-wDGGBC9r-fV987mnFPg8JSFhL-pt2cE_x5VomgSSmw2ZIU54sVSbG1yP63LMFXtq2UlwgkwKxv_35yivsmxzpAMyZG4lOZR5tf6KzWCCqRP5iyIaklgzzFoLOJRV0NULLgWQ7fnrJbhwPI_QyWAs1KMzQ8IqkTPMyZIip8ZIXDR1wSLCPyuOOGv8Yg-dHi1mt21vjly99iO76SZeATGU8kvm0afWQUZZPOG9kw5LFp57Um9uGMSIFvEseTbgWV0xXafyWOhVx7QNvtFIkg5wd1BzcQy-geIv2kpIw"

def get_fundamentals(symbol):
    url = f"https://api.tradezero.com/v1/fundamentals/api/fundamentals?symbols={symbol}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        print(data)
    else:
        print(f"Error: {response.status_code}")

get_fundamentals("AAPL")