
class SearchBook:

    def keys_word(self):
        user_key = input('Enter the word for search: ').strip().lower()

        recipe_name = None
        recipe_text = None
        found = False

        with open('sport_recipes.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line_low = line.lower().strip()

                if line_low.startswith('рецепт'):
                    recipe_name = line.strip()

                elif line_low.startswith('готовка'):
                    recipe_text = line.strip()

                   
                    if recipe_name and user_key in recipe_name.lower():
                        print('\nНайден рецепт:')
                        print(recipe_name)
                        print(recipe_text)
                        found = True

        if not found:
            print('Не найдено')
  

    def search_meal(self):

        recipes_count = 5
        count = 0
        read_recipes = False

        user_meal = input('Enter breakfast, lunch, dinner or drink:  ').strip().upper()

        with open('sport_recipes.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line_up = line.strip().upper()

                if line_up == user_meal:
                    read_recipes = True
                    continue

                if read_recipes:
                    if 'готовка' in line.lower():
                        print(line.strip())
                        print()
                    if  'рецепт' in line.lower():
                        print(line.strip())    
                        count += 1

                    if count == recipes_count:
                        count = 0
                        return    
            print('Не найдено')

    def search_by_cal(self):

        user_cal = int(input('Enter the desired number of calories per 100 grams:  ').strip())
        

        with open('sport_recipes.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line_low = line.lower()

                if line_low.startswith('рецепт'):
                    recipe_name = line.strip()
                elif line_low.startswith('готовка'):
                    recipe_text = line.strip() 

                if 'рецепт' in line_low:
                    parts = line_low.split()

                    for word in parts:
                        if word.isdigit():
                            calories = int(word)

                            if calories <= user_cal:
                                print(recipe_name)
                                print(recipe_text)
                
            print('Не найдено')        


class UserBook:

    def new_recipe(self):
        
        self.user_recipe_name = input('Enter the name of your recipe:  ').lower()
        self.user_recipe_text = input('How to prepare?:  ')

        print(f'Your resipe name:  {self.user_recipe_name}')
        print(f'Your text of recipe:  {self.user_recipe_text}')

        user_action = input('Do you want to save? YES/NO:  ').strip().upper()

        if user_action == 'YES':
            self.save_recipe()
        else: return    

    def save_recipe(self):
        
        with open('UserCookbook.txt', 'a', encoding='utf-8') as file:
            file.write(f'Рецепт: {self.user_recipe_name} ' + '\n') 
            file.write(f'Готовка: {self.user_recipe_text}' + '\n')

        user_action_save = input('Whould you like to add another recipe? YES/NO:  ').strip().upper()    

        if user_action_save == 'YES':
            self.new_recipe()
        else: return 



class Navigation:

    def menu(self):

        print('~ Welcome to the recipe book ~')
        print()
        print('=== Select an action ===')
        print('1 - Find a recipe by keyword')
        print('2 - Find a recipe by meal')
        print('3 - Find a recipe  by calorie count')
        print('4 - Create your own recipe')
        print('5 - Exit')

        
        return input('Enter the number:  ').strip()
    
s = SearchBook()    
u = UserBook()
                                       
actions = {
    '1': s.keys_word,
    '2': s.search_meal,
    '3': s.search_by_cal,
    '4': u.new_recipe,
    '5': exit
}    

n = Navigation()
choice = n.menu()       

action = actions.get(choice)

if action:
    action()     
else:
    print('Invalid choice')
