import time      # time.sleep
import bs4 as bs # processing HTML retrieved from Selenium
import re        # finding text by regular expressions
import os.path   # checking if scrape csv file is present

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

from webdriver_manager.chrome import ChromeDriverManager

from datetime import datetime, timedelta
from unidecode import unidecode # normalize (á -> a)superbid product name in order to create URL
from utils import get_credentials, create_url_pars

import pyotp                    # OTP functions
import pandas as pd             # tabular data


class Webscraper():

    DATA_FOLDER = 'scrape_data'
    TWITTER = 1
    TWITTER_FILE = 'twitter_scrape.csv'
    FACEBOOK_MP = 2
    FACEBOOK_FILE = 'facebook_scrape.csv'
    SUPERBID = 3
    SUPERBID_FILE = 'superbid_scrape.csv'

    def __init__(self, scrape_location:int):
        """Scraper initializer.

        Instantiate the Google Chrome browser, set parameters and
        constants to be used in following methods, e.g., scrape location and scrape data file name.

        Args:
            scrape_location (int) : One of the integer class attributes.
        """
        chrome_driver = ChromeService(ChromeDriverManager().install())
        chrome_options = webdriver.ChromeOptions() 
        chrome_options.add_argument("--headless")                           # this will make run browsing invisible
        # using headless with twitter cause error: https://stackoverflow.com/questions/70188027/chrome-headless-mode-not-working-however-normal-mode-is-working-fine
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        chrome_options.add_argument(f"--user-agent={user_agent}")           
        chrome_options.add_argument('--blink-settings=imagesEnabled=false') # this will disable image loading
        ## Attributes
        self.driver = webdriver.Chrome(service=chrome_driver, options=chrome_options) # initialize the Chrome driver
        self.WAITING_TIME = 5
        self.wait = WebDriverWait(self.driver, self.WAITING_TIME) # wait maximum X seconds
        self.scrape_location = scrape_location
        if scrape_location == self.TWITTER:
            self.scrape_file = self.TWITTER_FILE
        elif scrape_location == self.FACEBOOK_MP:
            self.scrape_file = self.FACEBOOK_FILE
        elif scrape_location == self.SUPERBID:
            self.scrape_file = self.SUPERBID_FILE

    def login(self) -> None:
        """Call according login function.

        Go to login pages and perform needed steps to login, such as username, password and OTP.

        Args:
            scrape_location (int) : One of the integer class attributes.

        Raises:
            NotImplementedError: In case self.scrape_location is not properly set.
        """
        # head to twitter login page
        if self.scrape_location == self.TWITTER:
            print('Logging into Twitter...')
            credentials = get_credentials('twitter')
            self.driver.get("https://twitter.com/i/flow/login")
            self.twitter_login(credentials['username'], credentials['password'], credentials['otp_key'])
        elif self.scrape_location == self.FACEBOOK_MP:
            print('Logging into Facebook...')
            parameters = get_credentials('facebook')
            credentials = parameters['credentials']
            self.driver.get("https://www.facebook.com/marketplace") # force login, have to reenter url afterwards
            self.facebook_marketplace_login(credentials['username'], credentials['password'])
        else:
            raise NotImplementedError("Only Twitter and Facebook Marketplace logins are implemented by now")

    def scrape(self, **kwargs:dict) -> None:
        """Call according scrape function.

        Go to scrape pages and perform needed steps to retrieve needed data.

        Args:
            kwargs (dict) : Parameters passed down to scrape functions.

        Raises:
            NotImplementedError: In case self.scrape_location is not properly set.
        """
        if self.scrape_location == self.TWITTER:
            print('Scraping Twitter Data...')
            df = self.twitter_scrape(**kwargs)
        elif self.scrape_location == self.FACEBOOK_MP:
            print('Scraping Facebook Marketplace Data...')
            df = self.facebook_marketplace_scrape(**kwargs)
        elif self.scrape_location == self.SUPERBID:
            print('Scraping Superbid Data...')
            df = self.superbid_scrape(**kwargs)
        else:
            raise NotImplementedError("Only Twitter, Facebook Marketplace, and Superbid are implemented by now")
        print('Saving and Updating File...')
        self.__update_and_save_scrape_file(df)
        print('Done.')

    def __get_bet_end_date(self, bet_end_date_text:str):
        """Process string to retrieve proper bet end date.

        Retrieve bet end date and create according datetime variable from multiple string formats.

        Args:
            bet_end_date_text (str) : Text extracted from HTML
        """
        # 1st case example: "Encerra em 1 dia"
        bet_end_tokens = bet_end_date_text.split(' ')
        is_token = [str.isdigit(elem) for elem in bet_end_tokens]
        is_token_true = [ix for ix,boolean in enumerate(is_token) if boolean]
        bet_end_date_return = ""
        if len(is_token_true) > 0:
            days_to_end = int(bet_end_tokens[is_token_true[0]])
            bet_end_date_return = (datetime.today() + timedelta(days=days_to_end)).strftime("%Y-%m-%d")
        elif ' - ' in bet_end_date_text : # 2nd case example: "Encerra em 18/05 - 14:00"
            colon_index = bet_end_date_text.index(":")
            hour_end = int(bet_end_date_text[colon_index-2:colon_index])
            bar_index = bet_end_date_text.index("/")
            day_end = int(bet_end_date_text[bar_index-2:bar_index])
            month_end = int(bet_end_date_text[bar_index+1:bar_index+3])
            bet_end_datetime = datetime.strptime(f"{datetime.now().year}-{month_end}-{day_end} {hour_end}:00", "%Y-%m-%d %H:%M")
            bet_end_date_return = bet_end_datetime.strftime("%Y-%m-%d")
        else: # 3rd case example: "Encerra em 22h"
            hours_finish = int(re.search('(\d+)h', bet_end_date_text).group(1))
            bet_end_date_return = (datetime.today() + timedelta(hours=hours_finish)).strftime("%Y-%m-%d")
        return bet_end_date_return

    def __update_and_save_scrape_file(self, df:pd.DataFrame) -> None:
        """Update scrape data file with new scraped data.

        Update csv file only with new retrieved data based on their IDs.

        Args:
            df (pd.DataFrame) : Scraped data from ``self.scrape``.
        """
        path_file = f'{self.DATA_FOLDER}/{self.scrape_file}'
        if os.path.isfile(path_file):
            df_temp = pd.read_csv(path_file, index_col=0)
            df_temp = pd.concat([df_temp, df])
            df = df_temp.drop_duplicates(subset='id', keep='last') # keep most recent data
        df.to_csv(path_file)

    def superbid_scrape(self, remove_duplicates:bool=True) -> pd.DataFrame:
        """Scrape data from superbid website.

        Run through superbid data, extract HTML and extract fields.

        Args:
            remove_duplicates (bool) : Whether to remove possible retrieved duplicated fields.

        Returns:
            Retrieved data frame.
        """
        query_filters_list = get_credentials('superbid')['query_filters']
        final_df = pd.DataFrame()
        for query_filters in query_filters_list:
            department = query_filters['department']
            print(f'...Querying Department = {department}...')
            del query_filters['department'] # it's not part of the pars url
            query_filters['pageNumber'] = 1 #### fixed parameters
            query_filters['pageSize'] = 60  #####################
            url = create_url_pars(f"https://www.superbid.net/categorias/{department}", query_filters)
#             print(url)

            self.driver.get(url)
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='MuiGrid-root MuiGrid-container MuiGrid-item MuiGrid-grid-xs-12 MuiGrid-grid-sm-5 MuiGrid-grid-md-4 css-vx8qp']")))

            page_source = self.driver.page_source
            soup = bs.BeautifulSoup(page_source, 'html.parser')

            # Get the items.
            div = soup.find_all('div', class_='MuiGrid-root MuiGrid-container MuiGrid-item MuiGrid-grid-xs-12 MuiGrid-grid-sm-5 MuiGrid-grid-md-4 css-vx8qp')
            product_names, urls, ids, prices, locations, bet_end_dates, img_sources, popularities = [], [], [], [], [], [], [], []
            for d in div:
                product_names.append(d['data-auction-name'])
                ids.append(d['data-auction-id'])
                prod_description = unidecode(d['data-auction-name']).lower()
                prod_description = re.split('\W+', prod_description)
                prod_description = '-'.join(prod_description)
                if prod_description[-1] == '-':
                    prod_description = prod_description[:-1]
                url = f"https://www.superbid.net/oferta/{prod_description}-{d['data-auction-id']}"
                urls.append(url)
                price = d.find_all(lambda tag: len(tag.find_all()) == 0 and "R$" in tag.text)[0].text # searching by text
                prices.append(price)
                location = d.find_all('img', src="./images/logo_location.png")[0].next_sibling.strip()
                locations.append(location)
                bet_end_tokens = d.find_all(lambda tag: len(tag.find_all()) == 0 and "Encerra" in tag.text)[0].text
                bet_end_date = self.__get_bet_end_date(bet_end_tokens)
                bet_end_dates.append(bet_end_date)
                img_source = d.find_all('img')[0]['src']
                img_sources.append(img_source)
                popularity = d.find_all('img', src="./images/logo_visits.png")[0].find_parent().text
                popularities.append(popularity)

            df = pd.DataFrame({'product_name': product_names,
                               'price': prices,
                               'url':urls,
                               'location': locations,
                               'bet_end_date': bet_end_dates,
                               'img_source':img_sources,
                               'popularity':popularities,
                               'id':ids})

            if remove_duplicates:
                df = df.drop_duplicates()
            df['department'] = department
            df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            final_df = pd.concat([final_df, df])

        return final_df


    def facebook_marketplace_login(self, username:str, password:str) -> None:
        """Login steps for Facebook Marketplace.

        Run through facebook login pages and insert login data.

        Args:
            username (str) : Username used to login at Facebook.
            password (str) : Password used to login at Facebook.
        """
        # find username/email field and send the username itself to the input field
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='email']"))).send_keys(username)
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='pass']"))).send_keys(password)
        # click login button
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@id='loginbutton']"))).click()

    def facebook_marketplace_scrape(self, n_scrolls:int=1, remove_duplicates:bool=True) -> pd.DataFrame:
        """Scrape steps for Facebook Marketplace.

        Run through facebook marketplace main results page and scrape data.

        Args:
            n_scrolls (int) : Number of ``PAGE DOWN`` button clicks to perform in the browser and load more items.
            remove_duplicates (bool) : Whether to remove possible retrieved duplicated fields.

        Returns:
            Retrieved data frame.
        """
        # Wait for the page to load.
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class=' x1gslohp x1e56ztr']")))

        query_filters_list = get_credentials('facebook')['query_filters']
        df_final = pd.DataFrame()
        for query_filters in query_filters_list:
            department = query_filters['department']
            print(f'...Querying Department = {department}...')
            del query_filters['department'] # it's not part of the pars url
            url = create_url_pars(f"https://www.facebook.com/marketplace/category/{department}", query_filters)
            print(url)
            self.driver.get(url) # force login, have to reenter url afterwards

            # Wait for the page to load.
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div[class=' x1gslohp x1e56ztr']")))

            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform() # test to dismiss notifications pop up

            for i in range(1, n_scrolls):
                # Scroll down to the bottom of the page to load all items.
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);")

                # Wait for the page to finish loading.
                time.sleep(self.WAITING_TIME)

            # Get the page source.
            page_source = self.driver.page_source
            soup = bs.BeautifulSoup(page_source, 'html.parser')

            # Get the items.
            div = soup.find_all('div', class_='x9f619 x78zum5 x1r8uery xdt5ytf x1iyjqo2 xs83m0k x1e558r4 x150jy0e xnpuxes x291uyu x1uepa24 x1iorvi4 xjkvuk6')

            # Iterate through the items.
            images_src, titles, prices, urls, ids, locations = [],[],[],[],[],[]
            for d in div:
                # Get the item image.
                img_ = d.find('img', class_='xt7dq6l xl1xv1r x6ikm8r x10wlt62 xh8yej3')
                image = img_['src'] if img_ is not None else None
                if img_ is not None:
                    images_src.append(image)
                    # Get the item title from span.
                    title_ = d.find('span', 'x1lliihq x6ikm8r x10wlt62 x1n2onr6')
                    title = title_.text if title_ is not None else None
                    titles.append(title)
                    # Get the item price.
                    price_ = d.find('span', 'x193iq5w xeuugli x13faqbe x1vvkbs xlh3980 xvmahel x1n0sxbx x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x x4zkp8e x3x7a5m x1lkfr7t x1lbecb7 x1s688f xzsf02u')
                    price = price_.text if price_ is not None else None
                    prices.append(price)
                    # Get the item URL.
                    url_ = d.find('a', class_='x1i10hfl xjbqb8w x6umtig x1b1mbwd xaqea5y xav7gou x9f619 x1ypdohk xt0psk2 xe8uvvx xdj266r x11i5rnm xat24cr x1mh8g0r xexx8yu x4uap5 x18d9i69 xkhd6sd x16tdsg8 x1hl2dhg xggy1nq x1a2a7pz x1heor9g x1lku1pv')
                    url = url_['href'] if url_ is not None else None
                    urls.append(f"https://www.facebook.com{url}")
                    # get item id from url
                    id_ = re.search('item/(\d+)/', url).group(1)
                    ids.append(id_)
                    # Get the item location.
                    location_ = d.find('span', 'x1lliihq x6ikm8r x10wlt62 x1n2onr6 xlyipyv xuxw1ft')
                    location = location_.text if location_ is not None else None
                    locations.append(location)
            df = pd.DataFrame({'title': titles,
                               'price': prices,
                               'url':urls,
                               'id': ids,
                               'location':locations,
                               'image_src': images_src})
            if remove_duplicates:
                df = df.drop_duplicates()
            df['department'] = department
            df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            df = self.facebook_marketplace_enrich(df)
            df_final = pd.concat([df_final, df])
        return df_final

    def facebook_marketplace_enrich(self, df:pd.DataFrame) -> pd.DataFrame:
        """Add extra informations for the items retrieved in the scrape function.

        Access each item page retrieved in the ``scrape`` function and extract more information.
        Function needs the ``url`` column from the retrieved items.

        Args:
            df (pd.DataFrame) : Data retrieved from Facebook Marketplace.

        Returns:
            Enriched data frame.
        """
        conditions, descriptions, times_posted = [], [],[]
        for ix, row in df.iterrows():
            if ix % 10 == 0:
                print(f'Enriching {10 * (ix // 10) + 10} items out of {df.shape[0]}')
            self.driver.get(row['url'])
            try: # make sure everything is loaded by checking one of the text fields <-- avoid time.sleep conditions
                self.wait.until(EC.presence_of_element_located((By.XPATH, ".//span[@class='x193iq5w xeuugli x13faqbe x1vvkbs xlh3980 xvmahel x1n0sxbx x6prxxf xvq8zen xo1l8bm xzsf02u']")))
            except Exception:
                pass
            page_source = self.driver.page_source
            soup = bs.BeautifulSoup(page_source, 'html.parser')
            condition = soup.find_all('span', class_='x193iq5w xeuugli x13faqbe x1vvkbs xlh3980 xvmahel x1n0sxbx x6prxxf xvq8zen xo1l8bm xzsf02u')
            condition = condition[0].text if len(condition) > 0 else ""
            conditions.append(condition)
            description = soup.find_all('span', class_='x193iq5w xeuugli x13faqbe x1vvkbs xlh3980 xvmahel x1n0sxbx x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x x4zkp8e x3x7a5m x6prxxf xvq8zen xo1l8bm xzsf02u')
            description = description[1].text if len(description) > 0 else ""
            descriptions.append(description)
            time_posted = soup.find_all('span', class_='x193iq5w xeuugli x13faqbe x1vvkbs xlh3980 xvmahel x1n0sxbx x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x x4zkp8e x676frb x1nxh6w3 x1sibtaa xo1l8bm xi81zsa')
            time_posted = time_posted[0].text if len(time_posted) > 0 else ""
            times_posted.append(time_posted)
        df['condition'] = conditions
        df['description'] = descriptions
        df['time_posted'] = times_posted
        return df

    def twitter_login(self, username:str, password:str, otp_key:str):
        """Login steps for Twitter.

        Run through Twitter login pages and insert login data.

        Args:
            username (str) : Username used to login at Twitter.
            password (str) : Password used to login at Twitter.
            otp_key (str) : One Time Password key.
        """
        # find username/email field and send the username itself to the input field
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='text']"))).send_keys(username)
        # click login button
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button'][contains(.,'Next')]"))).click()

        try:
            # find password input field and insert password as well
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='password']"))).send_keys(password)
            self.driver.find_element(By.XPATH, "//div[@role='button'][contains(.,'Log in')]").click()
        except (TimeoutException, NoSuchElementException) as error:
            # find username/email field and send the username itself to the input field
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='text']"))).send_keys('+5511949865898')
            # click login button
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button'][contains(.,'Next')]"))).click()
            # find password input field and insert password as well
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='password']"))).send_keys(password)
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button'][contains(.,'Log in')]"))).click()
        finally:
            # finally add OTP
            otp = totp = pyotp.TOTP(otp_key).now()
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='text']"))).send_keys(otp)
            # login
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button'][contains(.,'Next')]"))).click()
            time.sleep(self.WAITING_TIME+2)

    def twitter_scrape(self, n_scrolls:int=5, remove_duplicates:bool=True):
        """Scrape steps for Twitter.

        Run through Twitter main results page and scrape data.

        Args:
            n_scrolls (int) : Number of ``PAGE DOWN`` button clicks to perform in the browser and load more items.
            remove_duplicates (bool) : Whether to remove possible retrieved duplicated fields.

        Returns:
            Retrieved data frame.
        """

#         self.driver.get("https://twitter.com/home")
#         time.sleep(WAITING_TIME)

        df_final = pd.DataFrame()
        for i in range(n_scrolls):
            # Get the page source.
            page_source = self.driver.page_source
            soup = bs.BeautifulSoup(page_source, 'html.parser')

            tweet_texts, authors_handle, posts_id, posts_url, datetimes_posted, languages = [], [], [], [], [], []
            all_articles = soup.find_all('article')
            for article in all_articles:
                tweet_text = article.find_all('div', {'data-testid':'tweetText'})
                tweet_text = tweet_text[0].text if len(tweet_text) > 0 else ""
                tweet_texts.append(tweet_text)
                author_handler = re.split('@|·', article.find_all('div', {'data-testid':'User-Name'})[0].text)[1]
                authors_handle.append(author_handler)
                post_id = ''
                post_url = ''
                for al in article.find_all('a'):
                    url_match = re.match('.*status/\d+$', al['href'])
                    if url_match is not None:
                        post_id = al['href'].split('/')[-1]
                        post_url = f"https://twitter.com{al['href']}"
                        break
                posts_id.append(post_id)
                posts_url.append(post_url)
                language = article.find_all('div', {'data-testid':'tweetText'})
                language = language[0]['lang'] if len(language) > 0 else ""
                languages.append(language)
                datetime_posted = article.find_all('time')
                datetime_posted = datetime_posted[0]['datetime'] if len(datetime_posted) > 0 else None
                datetimes_posted.append(datetime_posted)
            df = pd.DataFrame({'id': posts_id,
                               'url': posts_url,
                               'tweet_text': tweet_texts,
                               'author_handle': authors_handle,
                               'datetime_posted': datetimes_posted,
                               'language':languages})
            df_final = pd.concat([df_final, df])

            for _ in range(3):
                ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
                time.sleep(0.5)
        df_final['tweet_text'] = df_final['tweet_text'].str.strip()
        if remove_duplicates: # remove duplicates before adding scraping time
            df_final = df_final.drop_duplicates(subset='id')
        df_final['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        return df_final
