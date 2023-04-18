import utils
from webscraper import Webscraper
if __name__ == '__main__':
    # ws = Webscraper(scrape_location=Webscraper.TWITTER)
    # ws.login()
    # ws.scrape(n_scrolls=40)

    ws = Webscraper(scrape_location=Webscraper.FACEBOOK_MP)
    ws.login()
    ws.scrape(n_scrolls=1)