import pandas as pd
from streetkitchen import CookBook, Recipe
from datetime import datetime


def recipe_to_df(urls: list):
    df = pd.concat([Recipe(url).agg() for url in urls])
    df.index.name = 'postid'
    df.reset_index(inplace=True)
    return df


def run(topic_list: list, posts_per_page: int, security: str, recipe_dl_num: int = 0):
    sk = CookBook()
    # print(list(sk.recipes.keys()))
    data_cb = sk.cookbook_download(topic_list=topic_list, posts_per_page=posts_per_page, security=security)
    if recipe_dl_num == 0:
        data_rp = recipe_to_df(urls=data_cb.url)
    else:
        data_rp = recipe_to_df(urls=data_cb.sample(recipe_dl_num).url)
    sk.to_xlsx(sheets={'cookbook': data_cb,
                       'recipes': data_rp},
               path=f'StreetKitchen (receptek)_{datetime.now().strftime("%Y-%m-%d-%H%M%S")}.xlsx')


if __name__ == '__main__':
    ####################################################################################################################
    # COOKBOOK
    ####################################################################################################################
    # topic_list = ['Fitt', 'Kids', 'Basic', 'INSTANT', 'Green Kitchen', 'A legjobb reggelik', 'Alapkészítmények',
    #               'Brutális fogások', 'Fantasztikus desszertek', 'Halak', 'Húst hússal', 'Italok',
    #               'Junk', 'Levesek és főzelékek', 'Megúszós sütik', 'Pékség', 'Megúszós kaják', 'Saláta',
    #               'Szendvicsek és burgerek', 'Tésztapolc', 'Vegetáriánus ételek']
    topic_list = ['A legjobb reggelik', 'Brutális fogások', 'Halak', 'Húst hússal',
                  'Junk', 'Levesek és főzelékek', 'Megúszós kaják', 'Szendvicsek és burgerek']
    run(topic_list=topic_list, posts_per_page=300, security='72a90dfa6a', recipe_dl_num=10)
