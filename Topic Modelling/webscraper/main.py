import utils
from webscraper import Webscraper

if __name__ == '__main__':
    ws = Webscraper(scrape_location=Webscraper.SUPERBID)
    ws.scrape()

    ws = Webscraper(scrape_location=Webscraper.FACEBOOK_MP)
    ws.login()
    ws.scrape()