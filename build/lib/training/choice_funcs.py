def get_digit_choice(input_text, invalid_text, range_low, range_top):
    choice = "not a number"
    while not isinstance(choice, int):
        choice = input(input_text)
        try:
            choice = int(choice)
            if choice < range_low or choice >= range_top:
                print(invalid_text)
                choice = "not a number"
        except:
            print(invalid_text)
            choice = "not a number"
    return choice

def get_yes_no_choice(input_text):
    choice = "not y or n"
    while choice.lower() not in ["y", "n"]:
        choice = input(input_text)
    return choice.lower()

def get_year(input_text):
    return get_digit_choice(input_text, "Invalid year. Please enter a year in the range (1920-2021).", 1920, 2022)

def get_month(input_text):
    return get_digit_choice(input_text, "Invalid month. Please enter a number (1-12) for the desired month.", 1, 13)

def get_day(input_text):
    return get_digit_choice(input_text, "Invalid date. Please enter a number (1-31) for the desired date.", 1, 32)