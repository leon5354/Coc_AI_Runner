import random

def d100_roll():
    """Returns a random integer between 1 and 100."""
    return random.randint(1, 100)

def check_success(skill_level, roll_result=None):
    """
    Checks if a skill roll is successful.
    Args:
        skill_level (int): The character's skill value (0-100).
        roll_result (int, optional): The dice roll. If None, rolls automatically.
    Returns:
        tuple: (status_string, roll_result)
    """
    if roll_result is None:
        roll_result = d100_roll()

    # Fumble/Crit Logic (Simplified CoC 7e)
    if roll_result == 1:
        return 'Critical Success', roll_result
    if roll_result >= 96 and skill_level < 50:
        return 'Fumble', roll_result
    if roll_result == 100:
        return 'Fumble', roll_result

    if roll_result <= skill_level:
        if roll_result <= skill_level / 5:
            return 'Extreme Success', roll_result
        elif roll_result <= skill_level / 2:
            return 'Hard Success', roll_result
        else:
            return 'Regular Success', roll_result
    else:
        return 'Failure', roll_result

def sanity_check(current_sanity, loss_value):
    """
    Performs a Sanity Check.
    Args:
        current_sanity (int): The investigator's current SAN score.
        loss_value (str or int): The SAN loss on failure (e.g., "1d4" or 5).
    Returns:
        tuple: (new_sanity, status, lost_amount)
    """
    roll = d100_roll()
    status = "Success" if roll <= current_sanity else "Failure"
    
    loss = 0
    if status == "Failure":
        # Parse loss value (e.g., "1d6", "1/1d4", "5")
        # For simplicity, if it's a string like "1d4", we roll it.
        if isinstance(loss_value, str) and 'd' in loss_value:
            num, sides = map(int, loss_value.split('d'))
            loss = sum(random.randint(1, sides) for _ in range(num))
        else:
            loss = int(loss_value)
    
    new_sanity = max(0, current_sanity - loss)
    return new_sanity, status, loss


if __name__ == '__main__':
    # Example usage
    roll = d100_roll()
    skill_level = 60
    result = check_success(roll, skill_level)
    print(f'Roll: {roll}, Skill Level: {skill_level}, Result: {result}')

    investigator = {'Sanity': 70}
    sanity_loss = 5
    updated_investigator = sanity_check(investigator, sanity_loss)
    print(f'Sanity before: {investigator["Sanity"]}, Sanity after: {updated_investigator["Sanity"]}')