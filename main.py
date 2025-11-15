import json
import random
import os
import sys
import datetime
from typing import List, Dict, Optional

DATA_DIR = "game_saves"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_SAVE_SLOTS = 4
WORLD_MAP = {
    'Town': ['Forest', 'Blacksmith', 'Inn'],
    'Forest': ['Town', 'Cave', 'Ruins'],
    'Cave': ['Forest', 'Underground Lake'],
    'Ruins': ['Forest', 'Ancient Temple'],
    'Ancient Temple': ['Ruins', 'Boss Lair'],
    'Boss Lair': [],
    'Blacksmith': ['Town'],
    'Inn': ['Town']
}


def save_path(slot:int) -> str:
    return os.path.join(DATA_DIR, f"save_slot_{slot}.json")


def now_ts():
    return datetime.datetime.utcnow().isoformat()

# -------------------------
# Base game entities
# -------------------------
class Item:
    def __init__(self, name: str, type_: str, power: int=0, value:int=0):
        self.name = name
        self.type = type_  # weapon, armor, consumable, material
        self.power = power
        self.value = value

    def to_dict(self):
        return {"name": self.name, "type": self.type, "power": self.power, "value": self.value}

    @staticmethod
    def from_dict(d):
        return Item(d['name'], d['type'], d.get('power',0), d.get('value',0))

class Equipment:
    def __init__(self):
        self.weapon: Optional[Item] = None
        self.armor: Optional[Item] = None

    def equip(self, item: Item):
        if item.type == 'weapon':
            self.weapon = item
        elif item.type == 'armor':
            self.armor = item

    def to_dict(self):
        return {"weapon": self.weapon.to_dict() if self.weapon else None, "armor": self.armor.to_dict() if self.armor else None}

    @staticmethod
    def from_dict(d):
        eq = Equipment()
        if d.get('weapon'):
            eq.weapon = Item.from_dict(d['weapon'])
        if d.get('armor'):
            eq.armor = Item.from_dict(d['armor'])
        return eq

# -------------------------
# Player & Classes
# -------------------------
class Player:
    def __init__(self, name:str, pclass:str='Warrior'):
        self.name = name
        self.pclass = pclass
        self.level = 1
        self.exp = 0
        self.health = self.max_health()
        self.gold = 100
        self.inventory: List[Item] = []
        self.equipment = Equipment()
        self.location = 'Town'
        self.story_progress = 0
        self.save_ts = now_ts()

    def max_health(self):
        base = 100
        if self.pclass == 'Warrior':
            base = 120
        elif self.pclass == 'Mage':
            base = 80
        elif self.pclass == 'Rogue':
            base = 90
        return base + (self.level - 1) * 10

    def attack_power(self):
        base = 10 + self.level * 2
        if self.pclass == 'Warrior':
            base += 4
        elif self.pclass == 'Mage':
            base -= 1
        elif self.pclass == 'Rogue':
            base += 1
        if self.equipment.weapon:
            base += self.equipment.weapon.power
        return base

    def defense(self):
        base = 2 + self.level
        if self.equipment.armor:
            base += self.equipment.armor.power
        return base

    def gain_exp(self, amount):
        self.exp += amount
        while self.exp >= self.exp_to_next():
            self.exp -= self.exp_to_next()
            self.level += 1
            self.health = self.max_health()
            print(f"*** {self.name} leveled up! Now level {self.level} ***")

    def exp_to_next(self):
        return 50 + (self.level - 1) * 20

    def add_item(self, item:Item):
        self.inventory.append(item)

    def remove_item(self, item_name:str) -> bool:
        for i, it in enumerate(self.inventory):
            if it.name == item_name:
                del self.inventory[i]
                return True
        return False

    def use_consumable(self, item_name:str):
        for i, it in enumerate(self.inventory):
            if it.name == item_name and it.type == 'consumable':
                # simple healing effect
                heal = it.power
                self.health = min(self.max_health(), self.health + heal)
                del self.inventory[i]
                print(f"You used {item_name} and healed {heal} HP.")
                return True
        print("No consumable by that name in inventory.")
        return False

    def to_dict(self):
        return {
            'name': self.name,
            'pclass': self.pclass,
            'level': self.level,
            'exp': self.exp,
            'health': self.health,
            'gold': self.gold,
            'inventory': [it.to_dict() for it in self.inventory],
            'equipment': self.equipment.to_dict(),
            'location': self.location,
            'story_progress': self.story_progress,
            'save_ts': self.save_ts
        }

    @staticmethod
    def from_dict(d):
        p = Player(d['name'], d.get('pclass','Warrior'))
        p.level = d.get('level',1)
        p.exp = d.get('exp',0)
        p.health = d.get('health', p.max_health())
        p.gold = d.get('gold',100)
        p.inventory = [Item.from_dict(it) for it in d.get('inventory',[])]
        p.equipment = Equipment.from_dict(d.get('equipment',{}))
        p.location = d.get('location','Town')
        p.story_progress = d.get('story_progress',0)
        p.save_ts = d.get('save_ts', now_ts())
        return p

# -------------------------
# Enemies and Bosses
# -------------------------
class Enemy:
    def __init__(self, name:str, health:int, power:int, loot:List[Item]=None, exp:int=10, gold:int=5):
        self.name = name
        self.health = health
        self.power = power
        self.loot = loot if loot else []
        self.exp = exp
        self.gold = gold

    def attack(self):
        return random.randint(1, self.power)

class Boss(Enemy):
    def __init__(self, name:str, health:int, power:int, phases:int=2, loot:List[Item]=None, exp:int=100, gold:int=200):
        super().__init__(name, health, power, loot, exp, gold)
        self.phases = phases

# -------------------------
# Crafting System
# -------------------------
CRAFT_RECIPES = {
    'Iron Sword': {'materials': {'Iron Ingot':2, 'Wood':1}, 'result': Item('Iron Sword','weapon',power=6,value=50)},
    'Health Potion': {'materials': {'Herb':3, 'Water':1}, 'result': Item('Health Potion','consumable',power=30,value=15)},
    'Leather Armor': {'materials': {'Leather':4}, 'result': Item('Leather Armor','armor',power=3,value=40)}
}

def craft_item(player:Player, recipe_name:str):
    rec = CRAFT_RECIPES.get(recipe_name)
    if not rec:
        print('Unknown recipe')
        return False
    mats = rec['materials']
    inv_counts = {}
    for it in player.inventory:
        inv_counts[it.name] = inv_counts.get(it.name,0) + 1
    for mat, need in mats.items():
        if inv_counts.get(mat,0) < need:
            print(f"Missing materials for {recipe_name}: need {need}x {mat}")
            return False
    # consume
    for mat, need in mats.items():
        to_remove = need
        new_inv = []
        for it in player.inventory:
            if it.name == mat and to_remove>0:
                to_remove -= 1
                continue
            new_inv.append(it)
        player.inventory = new_inv
    # add result
    player.add_item(rec['result'])
    print(f"Crafted {rec['result'].name}!")
    return True

# -------------------------
# Shops / NPCs
# -------------------------
class Shop:
    def __init__(self):
        # dynamic stock
        self.stock = {
            'Potion': Item('Potion','consumable',power=20,value=10),
            'Iron Ore': Item('Iron Ore','material',power=0,value=5),
            'Herb': Item('Herb','material',power=0,value=3),
            'Wood': Item('Wood','material',power=0,value=2)
        }

    def display(self):
        print('\n-- Shop Stock --')
        for name, item in self.stock.items():
            print(f"{name} - {item.value} gold ({item.type})")

    def buy(self, player:Player, item_name:str):
        it = self.stock.get(item_name)
        if not it:
            print('Item not available')
            return False
        if player.gold < it.value:
            print('Not enough gold')
            return False
        player.gold -= it.value
        player.add_item(it)
        print(f'Bought {item_name}')
        return True

    def sell(self, player:Player, item_name:str):
        for i,it in enumerate(player.inventory):
            if it.name == item_name:
                sell_price = max(1, it.value//2)
                player.gold += sell_price
                del player.inventory[i]
                print(f'Sold {item_name} for {sell_price} gold')
                return True
        print('You do not have that item')
        return False

def spawn_enemy_for_location(location:str) -> Enemy:
    if location == 'Forest':
        return Enemy('Goblin', health=40, power=8, loot=[Item('Herb','material',value=2)], exp=15, gold=8)
    if location == 'Cave':
        return Enemy('Cave Bat', health=30, power=6, loot=[Item('Iron Ore','material',value=5)], exp=12, gold=6)
    if location == 'Ruins':
        return Enemy('Skeleton', health=60, power=10, loot=[Item('Bone','material',value=1)], exp=20, gold=12)
    if location == 'Underground Lake':
        return Enemy('Water Serpent', health=80, power=14, loot=[Item('Scale','material',value=20)], exp=30, gold=20)
    return Enemy('Wandering Thief', health=35, power=7, loot=[Item('Gold Nugget','material',value=30)], exp=10, gold=10)

BOSS = Boss('Ancient Guardian', health=300, power=25, phases=3, loot=[Item('Guardian Core','material',value=500)], exp=500, gold=1000)

def encounter(player:Player):
    # random encounter based on location
    e = spawn_enemy_for_location(player.location)
    print(f"A wild {e.name} appears in the {player.location}!")
    combat(player, e)

# -------------------------
# Combat
# -------------------------

def combat(player:Player, enemy:Enemy):
    while enemy.health > 0 and player.health > 0:
        print(f"\n{player.name} HP: {player.health}/{player.max_health()}  |  {enemy.name} HP: {enemy.health}")
        action = input("Choose action: [a]ttack, [s]kill, [u]se item, [r]un: ")
        if action == 'a':
            damage = max(1, player.attack_power() - random.randint(0, enemy.power//2))
            enemy.health -= damage
            print(f"You strike {enemy.name} for {damage} damage")
        elif action == 's':
            # class-based skill
            if player.pclass == 'Warrior':
                dmg = player.attack_power() + 10
                enemy.health -= dmg
                print(f"Warrior Charge deals {dmg} damage!")
            elif player.pclass == 'Mage':
                dmg = 20 + player.level * 2
                enemy.health -= dmg
                print(f"Mage Fireball deals {dmg} damage!")
            elif player.pclass == 'Rogue':
                dmg = player.attack_power() + random.randint(5,15)
                enemy.health -= dmg
                print(f"Rogue Backstab deals {dmg} damage!")
        elif action == 'u':
            name = input('Item name to use: ')
            used = player.use_consumable(name)
            if not used:
                continue
        elif action == 'r':
            chance = random.random()
            if chance < 0.5:
                print('You escaped!')
                return
            else:
                print('Failed to escape!')
        else:
            print('Invalid action')
            continue
        # enemy turn
        if enemy.health > 0:
            ed = enemy.attack()
            # simple defense
            reduced = max(0, ed - player.defense()//2)
            player.health -= reduced
            print(f"{enemy.name} hits you for {reduced} damage")
    if player.health <= 0:
        print('You were defeated...')
        # simple death: lose half gold, respawn at town
        lost = player.gold//2
        player.gold -= lost
        player.health = player.max_health()
        player.location = 'Town'
        print(f'You wake up in Town, lost {lost} gold.')
    else:
        print(f'You defeated {enemy.name}!')
        player.gain_exp(enemy.exp)
        player.gold += enemy.gold
        for it in enemy.loot:
            player.add_item(it)
        print(f"Gained {enemy.exp} EXP and {enemy.gold} gold")

# Boss fight has phases

def boss_battle(player:Player, boss:Boss):
    print('\n--- BOSS ENCOUNTER: ' + boss.name + ' ---')
    phase = 1
    while boss.health>0 and player.health>0:
        print(f"Boss Phase {phase}: Boss HP {boss.health} | Player HP {player.health}/{player.max_health()}")
        combat_action = input('Attack (a) or Use Item (u): ')
        if combat_action == 'a':
            dmg = max(1, player.attack_power() - random.randint(0, boss.power//3))
            boss.health -= dmg
            print(f'You hit boss for {dmg}')
        elif combat_action == 'u':
            name = input('Item name: ')
            player.use_consumable(name)
        # boss retaliates with stronger attacks per phase
        if boss.health>0:
            bd = random.randint(1, boss.power + phase*5)
            player.health -= bd
            print(f'Boss hits you for {bd}')
        if boss.health < (boss.health // 2) and phase < boss.phases:
            phase += 1
            print('The boss enrages and enters phase', phase)
    if player.health <= 0:
        print('You were slain by the boss...')
        player.health = player.max_health()
        player.location = 'Town'
        player.gold = max(0, player.gold - 100)
        print('You wake up at the town healer, poorer but alive.')
    else:
        print('Boss defeated!')
        player.gain_exp(boss.exp)
        player.gold += boss.gold
        for it in boss.loot:
            player.add_item(it)

# -------------------------
# Save / Load (slots)
# -------------------------

def list_save_slots():
    slots = []
    for i in range(1, DEFAULT_SAVE_SLOTS+1):
        p = save_path(i)
        if os.path.exists(p):
            with open(p,'r') as f:
                try:
                    data = json.load(f)
                    slots.append((i, data.get('player',{}).get('name','<unknown>'), data.get('timestamp')))
                except Exception:
                    slots.append((i, '<corrupt>', None))
        else:
            slots.append((i, None, None))
    return slots

def save_to_slot(player:Player, slot:int):
    data = {'player': player.to_dict(), 'timestamp': now_ts()}
    with open(save_path(slot),'w') as f:
        json.dump(data,f,indent=2)
    print(f'Saved to slot {slot}')

def load_from_slot(slot:int) -> Optional[Player]:
    pth = save_path(slot)
    if not os.path.exists(pth):
        print('No save in that slot')
        return None
    with open(pth,'r') as f:
        data = json.load(f)
    return Player.from_dict(data['player'])

# -------------------------
# Game Menus
# -------------------------

def choose_class_menu():
    print('Choose a class:')
    print('1) Warrior — high health and strong melee')
    print('2) Mage — powerful spells, lower HP')
    print('3) Rogue — sneaky, high criticals')
    choice = input('>Select> ')
    mapping = {'1':'Warrior','2':'Mage','3':'Rogue'}
    return mapping.get(choice,'Warrior')


def main_menu():
    print('\n=== Welcome to The Ancient Path - Enhanced RPG ===')
    print('1) New Game')
    print('2) Load Game')
    print('3) List Save Slots')
    print('4) Quit')


def in_game_menu(player:Player, shop:Shop):
    print(f"\n-- {player.name} the {player.pclass} | Level {player.level} | HP {player.health}/{player.max_health()} | Gold {player.gold} | Loc: {player.location} --")
    print('1) Travel')
    print('2) Explore / Encounter')
    print('3) Inventory / Use / Equip')
    print('4) Crafting')
    print('5) Shop')
    print('6) Save Game')
    print('7) Boss Challenge (story)')
    print('8) View Stats')
    print('9) Exit to Main Menu')

# -------------------------
# Travel & Map navigation
# -------------------------

def travel_menu(player:Player):
    loc = player.location
    print(f'You are at {loc}. Adjacent locations: {WORLD_MAP.get(loc,[])}')
    choices = WORLD_MAP.get(loc, [])
    if not choices:
        print('No where to travel.')
        return
    for i, c in enumerate(choices, start=1):
        print(f'{i}) {c}')
    sel = input('Choose destination number: ')
    try:
        idx = int(sel)-1
        if idx < 0 or idx >= len(choices):
            print('Invalid')
            return
        newloc = choices[idx]
        player.location = newloc
        print(f'You travel to {newloc}')
    except Exception:
        print('Invalid')

# -------------------------
# Inventory / Equip
# -------------------------

def show_inventory(player:Player):
    print('\n-- Inventory --')
    if not player.inventory:
        print('Empty')
        return
    for i,it in enumerate(player.inventory,start=1):
        print(f"{i}) {it.name} ({it.type}) - Power:{it.power} Value:{it.value}")

def equip_menu(player:Player):
    show_inventory(player)
    choice = input('Enter item name to equip (weapon/armor) or blank: ')
    if not choice:
        return
    for it in player.inventory:
        if it.name == choice and it.type in ('weapon','armor'):
            player.equipment.equip(it)
            print(f'Equipped {it.name}')
            return
    print('Item not equippable or not found')

# -------------------------
# Crafting Menu
# -------------------------

def crafting_menu(player:Player):
    print('\n-- Crafting Station --')
    print('Available recipes:')
    for name, rec in CRAFT_RECIPES.items():
        print(f"{name}: requires {', '.join([f'{k}x{v}' for k,v in rec['materials'].items()])}")
    choice = input('Enter recipe name to craft or blank: ')
    if not choice:
        return
    craft_item(player, choice)

# -------------------------
# Shop Menu
# -------------------------

def shop_menu(player:Player, shop:Shop):
    while True:
        shop.display()
        print('Commands: buy <name>, sell <name>, exit')
        cmd = input('> ')
        if cmd.startswith('buy '):
            name = cmd[4:]
            shop.buy(player, name)
        elif cmd.startswith('sell '):
            name = cmd[5:]
            shop.sell(player, name)
        elif cmd == 'exit':
            break
        else:
            print('Unknown command')

# -------------------------
# Story & Quests
# -------------------------

def story_progression(player:Player):
    if player.story_progress == 0 and player.location == 'Ruins':
        print('\nYou discover an inscription hinting at a sealed guardian deep in the Ancient Temple.')
        player.story_progress = 1
    elif player.story_progress == 1 and player.location == 'Ancient Temple':
        print('\nA puzzle opens a passage to the Boss Lair.')
        player.story_progress = 2

# Boss challenge if conditions met

def attempt_boss(player:Player):
    if player.location != 'Boss Lair' and player.story_progress < 2:
        print('The way is sealed. You must progress the story to enter the Boss Lair.')
        return
    # copy boss for fight
    boss_copy = Boss(BOSS.name, BOSS.health, BOSS.power, BOSS.phases, loot=BOSS.loot, exp=BOSS.exp, gold=BOSS.gold)
    boss_battle(player, boss_copy)
    if boss_copy.health <= 0:
        print('With the Guardian defeated the world feels at peace... You completed the main story!')
        player.story_progress = 99

# -------------------------
# Main Game Loop
# -------------------------

def play_game(player:Player):
    shop = Shop()
    while True:
        in_game_menu(player, shop)
        choice = input('Choose> ')
        if choice == '1':
            travel_menu(player)
            # after move, maybe story hint
            story_progression(player)
        elif choice == '2':
            encounter(player)
        elif choice == '3':
            print('\n1) Show inventory 2) Equip item 3) Use consumable 0) Back')
            sub = input('> ')
            if sub == '1':
                show_inventory(player)
            elif sub == '2':
                equip_menu(player)
            elif sub == '3':
                name = input('Item name to use: ')
                player.use_consumable(name)
        elif choice == '4':
            crafting_menu(player)
        elif choice == '5':
            shop_menu(player, shop)
        elif choice == '6':
            print('Save to which slot?')
            slots = list_save_slots()
            for s in slots:
                print(s)
            slot = int(input('Slot number: '))
            save_to_slot(player, slot)
        elif choice == '7':
            attempt_boss(player)
        elif choice == '8':
            print(json.dumps(player.to_dict(), indent=2))
        elif choice == '9':
            confirm = input('Exit to main menu? (y/n) ')
            if confirm.lower()=='y':
                break
        else:
            print('Invalid')

# -------------------------
# Entrypoint
# -------------------------

def start():
    while True:
        main_menu()
        sel = input('> ')
        if sel == '1':
            name = input('Enter character name: ')
            pclass = choose_class_menu()
            player = Player(name, pclass)
            print(f'Created {player.name} the {player.pclass}')
            play_game(player)
        elif sel == '2':
            print('Select slot to load:')
            slots = list_save_slots()
            for s in slots:
                print(s)
            slot = int(input('Slot: '))
            p = load_from_slot(slot)
            if p:
                print(f'Loaded {p.name}')
                play_game(p)
        elif sel == '3':
            slots = list_save_slots()
            for s in slots:
                print(s)
        elif sel == '4':
            print('Goodbye!')
            sys.exit(0)
        else:
            print('Invalid choice')

if __name__ == '__main__':
    start()

