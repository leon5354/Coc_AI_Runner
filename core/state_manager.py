import json
import os

def load_game_state(filename='data/saves/game_state.json'):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            game_state = json.load(f)
        return game_state
    except FileNotFoundError:
        return {}

def save_game_state(game_state, filename='data/saves/game_state.json'):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(game_state, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    # Example usage
    initial_state = {'scene': 'Corbitt House Exterior', 'clues_found': []}
    save_game_state(initial_state)
    loaded_state = load_game_state()
    print(f'Loaded game state: {loaded_state}')