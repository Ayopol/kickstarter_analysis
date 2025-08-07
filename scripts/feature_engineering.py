
# import pandas as pd

# class GoalRatioEncoder:
#     def __init__(self):
#         self.mean_goal_by_cat = None
#         self.mean_goal_by_country = None

#     def fit(self, df):
#         self.mean_goal_by_cat = df.groupby('main_category')['usd_goal_real'].mean().to_dict()
#         self.mean_goal_by_country = df.groupby('country')['usd_goal_real'].mean().to_dict()

#     def transform(self, df):
#         df = df.copy()
#         df['ratio_goal_by_main_category'] = df.apply(
#             lambda row: row['usd_goal_real'] / self.mean_goal_by_cat.get(row['maincategory'], 1),
#             axis=1
#         )
#         df['ratio_goal_by_country'] = df.apply(
#             lambda row: row['usd_goal_real'] / self.mean_goal_by_country.get(row['country'], 1),
#             axis=1
#         )
#         return df



# ### drop the whole file ???????????????????????????????
