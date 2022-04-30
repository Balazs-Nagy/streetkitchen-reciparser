import requests
import bs4
from bs4 import BeautifulSoup
import pandas as pd
from numpy import nan
import time


class CookBook:
    def __init__(self):
        self.home = 'https://streetkitchen.hu/'
        self.request_url = f'{self.home}wp-admin/admin-ajax.php'

    @property
    def recipes(self):
        r = requests.get(self.home)
        soup = BeautifulSoup(r.content, 'html.parser')
        sub_menu = soup.find('div', {'class': 'sub-menu-wrapper'}).ul.find_all('li')
        recipes = {item.text.strip(): dict(url=item.a['href'],
                                           category_name=item.a['href'].split('/')[-2])
                   for item in sub_menu}
        return recipes

    @staticmethod
    def get_payload(action: str = 'be_ajax_load_more',
                    page: int = 1,
                    category_name: str = 'szendvicsek-es-burgerek',
                    posts_per_page: int = 10,
                    security: str = '72a90dfa6a',
                    related: int = 0,
                    search: int = 0,
                    exclude_post_list: str = 'false'
                    ):
        payload = {
                    'action': action,
                    'page': page,
                    'query[category_name]': category_name,
                    'query[posts_per_page]': posts_per_page,
                    'security': security,
                    'related': related,
                    'search': search,
                    'exclude_post_list': exclude_post_list
        }
        return payload

    @staticmethod
    def post(url: str, payload: dict) -> requests.models.Response:
        r = requests.post(url, data=payload)
        if r.status_code != 200:
            raise RuntimeError(r.status_code, r.ok, r.text, payload)
        return r

    @staticmethod
    def get_articles(response: requests.models.Response) -> list:
        soup = BeautifulSoup(response.json()['data'], 'html.parser')
        articles = soup.find_all('article')
        return articles

    @staticmethod
    def parse_article_features(article: bs4.BeautifulSoup) -> tuple:
        # id
        try:
            postid = article.div['data-postid']
        except KeyError:
            postid = [item for item in article['class'] if item.startswith('post-')][0].replace('post-', '')
        # entry-title
        title = article.find('h2', {'class': 'entry-title'}).a.text
        url = article.find('h2', {'class': 'entry-title'}).a['href']
        # entry-summary
        try:
            summary = article.find('div', {'class': 'entry-summary'}).text.strip()
        except AttributeError:
            summary = nan
        # entry-image
        try:
            img_url = article.find('div', {'class': 'entry-image'}).img['streetkitchen']
        except (TypeError, AttributeError):
            img_url = nan
        # entry-category
        cat_title = article.find('div', {'class': 'entry-category'}).text.strip()
        cat_url = article.find('div', {'class': 'entry-category'}).a['href']
        # article class (contains info on tags and categories in raw format)
        article_class = article['class']  # ', '.join(article['class'])

        article_features = (postid, title, url, summary, img_url, cat_title, cat_url, article_class)
        return article_features

    def post_to_df(self, topic: str = 'Szendvicsek és burgerek',
                   page: int = 1, posts_per_page: int = 10, security: str = '72a90dfa6a') -> pd.DataFrame:
        # the following features are parsed using the get_articles() method in this exact ordering
        columns = ('postid', 'title', 'url', 'summary', 'img_url', 'cat_title', 'cat_url', 'article_class')
        # generate payload for post request
        payload = self.get_payload(page=page, category_name=self.recipes[topic]['category_name'],
                                   posts_per_page=posts_per_page, security=security)
        # post request and fetch response
        response = self.post(url=self.request_url, payload=payload)
        # parse articles
        articles = self.get_articles(response=response)
        # list of tuples to dataframe
        df = pd.DataFrame([self.parse_article_features(article) for article in articles], columns=columns)
        # possible that there are multiple entries
        df.drop_duplicates(subset=df.drop('article_class', axis=1).columns, inplace=True)
        # insert main topic
        df.insert(loc=0, column='topic', value=topic)
        # extract category and tag info
        for col in ['category', 'tag']:
            df[col] = self.parse_article_class(df=df, string=f'{col}-', clear=True)
        # some values are duplicated (two images with different sizes are given and they are in a separate article tag)
        df.drop_duplicates(subset=['postid'], keep='last', inplace=True)
        # convert post-id to integer
        df.postid = df.postid.astype(int)
        # wheter there is video for the recipe
        df['video'] = (df.category.str.contains('video') | df.tag.str.contains('video')).map({True: 1, False: nan})
        # df.set_index('postid', inplace=True)
        df.reset_index(drop=True)
        return df

    @staticmethod
    def parse_article_class(df: pd.DataFrame, string: str, clear: bool = False) -> pd.Series:
        if clear:
            series = df.article_class.apply(lambda x: ', '.join([item.replace(f'{string}', '')
                                                                 for item in x if item.startswith(string)]))
        else:
            series = df.article_class.apply(lambda x: ', '.join([item
                                                                 for item in x if item.startswith(string)]))
        series.name = string.replace('-', '')
        return series

    def cookbook_download(self, topic_list: list, posts_per_page: int = 10, security: str = '72a90dfa6a') -> pd.DataFrame:
        delay = 5  # wait 5 seconds between requests
        dfs = []
        for topic in topic_list:
            print(topic)
            dfs.append(self.post_to_df(topic=topic, page=1, posts_per_page=posts_per_page, security=security))
            time.sleep(delay)
        df = pd.concat(dfs).reset_index(drop=True)
        return df

    @staticmethod
    def to_xlsx(sheets: dict, path: str):
        with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
            for sheet_name, df in sheets.items():
                # write data to sheet
                df.to_excel(writer, sheet_name=sheet_name, index=False, freeze_panes=(1, 0))
                # apply auto-filter
                writer.sheets[sheet_name].autofilter(0, 0, df.shape[0], df.shape[1] - 1)


class Recipe:
    def __init__(self, url: str):
        self.url = url
        # get link
        response = requests.get(url)
        # parse html
        self.soup = BeautifulSoup(response.content, 'html.parser')
        # main container
        self.main = self.soup.find('main', {'class': 'main'})
        self.ingredients_soup = self.main.find('div', {'class': 'ingredients-content'})
        # self.ingredient_groups_soup = self.ingredients_soup.find_all('div', {'class': 'ingredient-group'})

    @staticmethod
    def parse_ingredient_group(ingredient_group: bs4.element.Tag):
        items = [ig.text.strip().split('\n') for ig in ingredient_group.find_all('dd')]
        try:
            ig_title = ingredient_group.h3.text
        except AttributeError:
            ig_title = nan

        ig_content = [' '.join([i.strip() for i in item if i.strip() != '']) for item in items]
        return {ig_title: ig_content}

    @property
    def _ingredients(self) -> dict:
        ingredient_groups = self.ingredients_soup.find_all('div', {'class': 'ingredient-group'})
        ingredient_dict = {}
        for ig in ingredient_groups:
            ingredient_dict.update(self.parse_ingredient_group(ig))
        return ingredient_dict

    @property
    def _portion_size(self) -> str:
        # number of persons
        size = self.ingredients_soup.find('div', {'class': 'quantity-box'}).text.replace('\n', '')
        return size

    @property
    def _title(self):
        # entry title
        return self.main.find('h1', {'class': 'entry-title'}).text.strip()

    @property
    def _video_url(self):
        # video url
        try:
            return self.main.find('div', {'class': 'rll-youtube-player'})['data-streetkitchen']
        except TypeError:
            return nan

    @property
    def _category(self):
        cat = {
            'cat_title': self.main.find('div', {'class': 'entry-category'}).text.strip(),
            'cat_url': self.main.find('div', {'class': 'entry-category'}).a.get('href', nan)
        }
        return cat

    @property
    def _entry_lead(self):
        return self.main.find('div', {'class': 'entry-lead'}).text.strip()

    @property
    def _author(self):
        author_vcard = {}
        vcard = self.main.find('div', {'class': 'byline author vcard'})
        author_vcard['author_name'] = vcard.find('span').text.strip()
        author_vcard['author_url'] = vcard.a.get('href')
        author_vcard['author_img'] = vcard.img.get('data-lazy-streetkitchen')
        author_vcard['date'] = [t.text.replace(' ', '') for t in vcard.find_all('time')
                                if t.get('datetime', '') != ''][0]
        return author_vcard

    @property
    def _tags_list(self):
        return {li.text.strip(): li.a.get('href') for li in self.main.find('ul', {'class': 'tags-list'}).find_all('li')}

    @property
    def _article_class(self) -> dict:
        return {'article_class': self.main.find('article').get('class')}

    @property
    def _content(self) -> str:
        content = []
        exclude_tags = ['figure', 'img', 'picture']
        for tag in self.main.find('div', {'class': 'the-content-div'}).findChildren():
            if (tag.name == 'ul') & (tag.get('class') == ['tags-list']):
                # stopping rule
                break
            if tag.name not in exclude_tags:
                txt = tag.text.strip()
                if txt != '':
                    content.append(txt)
        content = ' '.join(content)
        return content

    def agg(self):
        results = {'title': self._title,
                   'lead': self._entry_lead}
        results.update(self._category)
        results.update(self._author)
        results.update({'content': self._content,
                        'portion_size': self._portion_size,
                        'ingredients': self._ingredients,
                        'video_url': self._video_url,
                        'tags_list': self._tags_list})

        id_col = nan
        for item in self._article_class['article_class']:
            if item[:5] == 'post-':
                id_col = [int(item.replace('post-', ''))]
                break
        results = pd.DataFrame.from_dict(results, orient='index',
                                         columns=id_col).T
        return results
