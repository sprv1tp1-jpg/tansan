import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import random
import math
from flask import Flask
from threading import Thread
import time

# Load the token from a .env file
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configure bot permissions
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create a bot instance to handle commands
bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to manage members to be excluded from auto group selection
excluded_members = {}
# Dictionary to manage members who are to be "carried"
carried_members = {}
# New: Dictionary to manage members who are "fixed" in a team
fixed_teams = {}
# New: Dictionary to manage members who are "preferred" for a fixed team
preferred_members = {}

# Define professions and their roles
PROFESSIONS = {
    '剣士': '前衛',
    '騎士': '前衛',
    '魔導士': '後衛',
    '賢者': '後衛'
}

# Overall ranking list (name, profession, power)
OVERALL_RANKS = [
    {'name': 'ちるっと', 'profession': '剣士', 'power': 2000},
    {'name': 'ほんあり', 'profession': '騎士', 'power': 1980},
    {'name': 'ひらぱー', 'profession': '魔導士', 'power': 1960},
    {'name': '炭酸', 'profession': '魔導士', 'power': 1940},
    {'name': 'きゅーりー', 'profession': '騎士', 'power': 1920},
    {'name': 'chami', 'profession': '魔導士', 'power': 1900},
    {'name': 'ノク', 'profession': '魔導士', 'power': 1880},
    {'name': '金パチ', 'profession': '賢者', 'power': 1860},
    {'name': 'Jackal', 'profession': '魔導士', 'power': 1840},
    {'name': 'シュシュリカ', 'profession': '賢者', 'power': 1820},
    {'name': '乳酸菌', 'profession': '魔導士', 'power': 1800},
    {'name': 'もや', 'profession': '騎士', 'power': 1780},
    {'name': 'かなり', 'profession': '剣士', 'power': 1760},
    {'name': 'つきみや', 'profession': '魔導士', 'power': 1740},
    {'name': 'おなまえ', 'profession': '賢者', 'power': 1720},
    {'name': 'ことりり', 'profession': '魔導士', 'power': 1700},
    {'name': 'Coco', 'profession': '魔導士', 'power': 1680},
    {'name': 'しの', 'profession': '賢者', 'power': 1660},
    {'name': 'せど', 'profession': '剣士', 'power': 1640},
    {'name': 'kazu', 'profession': '魔導士', 'power': 1620},
    {'name': 'もん', 'profession': '剣士', 'power': 1600},
    {'name': 'あい', 'profession': '剣士', 'power': 1580},
    {'name': 'INTP', 'profession': '賢者', 'power': 1560},
    {'name': 'Tera', 'profession': '魔導士', 'power': 1540},
    {'name': 'JIN', 'profession': '賢者', 'power': 1520},
    {'name': '96', 'profession': '魔導士', 'power': 1500},
    {'name': 'しらす', 'profession': '賢者', 'power': 1480},
    {'name': 'ジークアクス', 'profession': '騎士', 'power': 1460},
    {'name': 'くにお', 'profession': '剣士', 'power': 1440},
    {'name': 'みんふぁ', 'profession': '魔導士', 'power': 1420},
    {'name': 'ぽんずー', 'profession': '魔導士', 'power': 1400},
    {'name': 'らいち', 'profession': '剣士', 'power': 1380},
    {'name': 'ぽりんきー', 'profession': '剣士', 'power': 1360},
    {'name': 'おとも', 'profession': '魔導士', 'power': 1340},
    {'name': 'ぱんどら', 'profession': '騎士', 'power': 1320},
    {'name': 'うさちゃ', 'profession': '魔導士', 'power': 1300},
    {'name': '黒紫音', 'profession': '剣士', 'power': 1280}
]

# Generate profession-specific power rankings
PLAYER_RANKS = {}

def rebuild_player_ranks():
    """Helper function to rebuild PLAYER_RANKS from OVERALL_RANKS"""
    PLAYER_RANKS.clear()
    for profession in PROFESSIONS:
        PLAYER_RANKS[profession] = sorted([
            (p['name'], p['power']) for p in OVERALL_RANKS if p['profession'] == profession
        ], key=lambda x: x[1], reverse=True)

rebuild_player_ranks()

# Initialize list of leader candidates
LEADER_CANDIDATES = [
    'きゅーりー', 'もや', '炭酸', 'INTP', 'シュシュリカ', 'しの', 'つきみや', 'ぽんずー', '96'
]

def get_power_from_rank(profession, member_name):
    """
    Helper function to get power based on profession and member name.
    """
    ranks = PLAYER_RANKS.get(profession)
    if ranks:
        for name, power in ranks:
            if name == member_name:
                return power
    return None

# Autocomplete helper function for all member names
async def all_member_autocomplete(interaction: discord.Interaction, current: str):
    """
    Helper function to generate autocomplete choices for all member names.
    """
    members = [p['name'] for p in OVERALL_RANKS]
    return [
        app_commands.Choice(name=member, value=member)
        for member in members if current.lower() in member.lower()
    ][:25]

@bot.event
async def on_ready():
    """Event handler that runs when the bot is ready"""
    print(f'{bot.user.name} が正常に起動しました！')
    
    # Sync slash commands with Discord
    try:
        print("コマンドの同期を開始します...")
        synced = await bot.tree.sync()
        print(f'{len(synced)} 個のコマンドを同期しました。')
    except Exception as e:
        print(f'コマンドの同期中にエラーが発生しました: {e}')
    
    print('------')

@bot.tree.command(name='add_member', description='新しいメンバーを戦力リストに追加します。')
@app_commands.describe(member_name='追加するメンバーの名前', profession='メンバーの職業 (剣士, 騎士, 魔導士, 賢者)', power='メンバーの戦力値')
async def add_member(interaction: discord.Interaction, member_name: str, profession: str, power: int):
    """
    Adds a new member to the power list.
    """
    # Check if profession is valid
    if profession not in PROFESSIONS:
        await interaction.response.send_message(f'無効な職業です。利用可能な職業: {", ".join(PROFESSIONS.keys())}')
        return

    # Check if member already exists
    if any(p['name'] == member_name for p in OVERALL_RANKS):
        await interaction.response.send_message(f'`{member_name}`さんはすでに登録されています。')
        return

    # Add the member
    new_member = {'name': member_name, 'profession': profession, 'power': power}
    OVERALL_RANKS.append(new_member)
    
    # Rebuild rankings
    rebuild_player_ranks()

    await interaction.response.send_message(f'`{member_name}`さん ({profession}, 戦力: {power})を戦力リストに追加しました。')

@bot.tree.command(name='remove_member', description='戦力リストからメンバーを削除します。')
@app_commands.describe(member_name='削除するメンバーの名前')
@app_commands.autocomplete(member_name=all_member_autocomplete)
async def remove_member(interaction: discord.Interaction, member_name: str):
    """
    Removes a member from the power list.
    """
    global OVERALL_RANKS
    
    # Find the member in the list
    member_to_remove = next((p for p in OVERALL_RANKS if p['name'] == member_name), None)

    if member_to_remove:
        OVERALL_RANKS.remove(member_to_remove)
        
        # Rebuild rankings
        rebuild_player_ranks()
        
        await interaction.response.send_message(f'`{member_name}`さんを戦力リストから削除しました。')
    else:
        await interaction.response.send_message(f'`{member_name}`さんは戦力リストに見つかりませんでした。')

@bot.tree.command(name='rename_member', description='メンバーの名前を変更します。')
@app_commands.describe(old_name='変更前のメンバーの名前', new_name='新しいメンバーの名前')
@app_commands.autocomplete(old_name=all_member_autocomplete)
async def rename_member(interaction: discord.Interaction, old_name: str, new_name: str):
    """
    Changes a member's name.
    """
    # Find the member in the overall ranking list
    member_to_rename = next((p for p in OVERALL_RANKS if p['name'] == old_name), None)

    if not member_to_rename:
        await interaction.response.send_message(f'`{old_name}`さんは戦力リストに見つかりませんでした。')
        return

    # Check if the new name already exists
    if any(p['name'] == new_name for p in OVERALL_RANKS):
        await interaction.response.send_message(f'`{new_name}`はすでに他のメンバーが使用しています。')
        return
    
    # Update the name in the overall ranking
    member_to_rename['name'] = new_name
    
    # Update the name in the leader candidate list
    if old_name in LEADER_CANDIDATES:
        LEADER_CANDIDATES[LEADER_CANDIDATES.index(old_name)] = new_name
    
    # Update the name in the excluded members list
    user_id = interaction.user.id
    if user_id in excluded_members:
        if old_name in excluded_members[user_id]:
            excluded_members[user_id].remove(old_name)
            excluded_members[user_id].append(new_name)
    
    # Update the name in the carried members list
    if user_id in carried_members:
        if old_name in carried_members[user_id]:
            carried_members[user_id].remove(old_name)
            carried_members[user_id].append(new_name)
            
    # Update the name in the fixed members list
    if user_id in fixed_teams:
        if old_name in fixed_teams[user_id]:
            fixed_teams[user_id].remove(old_name)
            fixed_teams[user_id].append(new_name)
            
    # Update the name in the preferred members list
    if user_id in preferred_members:
        if old_name in preferred_members[user_id]:
            preferred_members[user_id].remove(old_name)
            preferred_members[user_id].append(new_name)


    # Rebuild rankings
    rebuild_player_ranks()

    await interaction.response.send_message(f'メンバー名 `{old_name}` を `{new_name}` に変更しました。')

@bot.tree.command(name='set_power', description='メンバーの戦力値を変更します。')
@app_commands.describe(member_name='戦力値を変更するメンバーの名前', new_power='新しい戦力値')
@app_commands.autocomplete(member_name=all_member_autocomplete)
async def set_power(interaction: discord.Interaction, member_name: str, new_power: int):
    """
    Changes a member's power value.
    """
    member_to_update = next((p for p in OVERALL_RANKS if p['name'] == member_name), None)

    if not member_to_update:
        await interaction.response.send_message(f'`{member_name}`さんは戦力リストに見つかりませんでした。')
        return

    member_to_update['power'] = new_power
    rebuild_player_ranks()

    await interaction.response.send_message(f'`{member_name}`さんの戦力値を `{new_power}` に変更しました。')

@bot.tree.command(name='member_list', description='すべてのメンバーと詳細な情報を表示します。')
async def member_list(interaction: discord.Interaction):
    """
    Displays a list of all registered members with their details.
    """
    message = '**メンバーリスト**\n'
    for i, member in enumerate(OVERALL_RANKS):
        message += f'{i + 1}. 名前: {member["name"]}, 職業: {member["profession"]}, 戦力: {member["power"]}\n'
    await interaction.response.send_message(message)

@bot.tree.command(name='set_carried', description='特定のメンバーをキャリー対象として設定します。')
@app_commands.describe(member_names='キャリー対象に設定するメンバーの名前 (スペース区切り)')
async def set_carried(interaction: discord.Interaction, member_names: str):
    """
    Sets one or more members as "carried" members.
    Note: Autocomplete is not supported for space-separated arguments.
    """
    user_id = interaction.user.id
    if user_id not in carried_members:
        carried_members[user_id] = []

    added_members = []
    not_found_members = []
    
    names_list = member_names.split()

    for member_name in names_list:
        if member_name not in [p['name'] for p in OVERALL_RANKS]:
            not_found_members.append(member_name)
        elif member_name in carried_members[user_id]:
            pass
        else:
            carried_members[user_id].append(member_name)
            added_members.append(member_name)
    
    message = ''
    if added_members:
        message += f'`{", ".join(added_members)}`さんをキャリー対象に設定しました。\n'
    
    if not_found_members:
        message += f'⚠️ 登録されていないメンバー: `{", ".join(not_found_members)}`'

    if not message:
        message = '指定されたメンバーはすべてすでにキャリー対象に設定されています。'

    await interaction.response.send_message(message)

@bot.tree.command(name='clear_carried', description='キャリー対象メンバーリストをリセットします。')
async def clear_carried(interaction: discord.Interaction):
    """
    Resets the list of carried members.
    """
    user_id = interaction.user.id
    if user_id in carried_members:
        carried_members[user_id] = []
        await interaction.response.send_message('キャリー対象メンバーリストをリセットしました。')
    else:
        await interaction.response.send_message('キャリー対象メンバーリストはすでに空です。')

@bot.tree.command(name='swap_power', description='指定された2人のメンバーの戦力値を交換します。')
@app_commands.describe(member1='1人目のメンバー', member2='2人目のメンバー')
@app_commands.autocomplete(member1=all_member_autocomplete, member2=all_member_autocomplete)
async def swap_power(interaction: discord.Interaction, member1: str, member2: str):
    """
    Swaps the power values of two specified members.
    """
    member1_name = member1
    member2_name = member2

    # Check if members exist, return None if not found
    member1 = next((p for p in OVERALL_RANKS if p['name'] == member1_name), None)
    member2 = next((p for p in OVERALL_RANKS if p['name'] == member2_name), None)

    if not member1 or not member2:
        await interaction.response.send_message('指定されたメンバーが見つかりません。フルネームを正しく入力してください。')
        return

    # Swap power values
    member1_power = member1['power']
    member2_power = member2['power']
    member1['power'] = member2_power
    member2['power'] = member1_power

    # Rebuild profession-specific rankings
    rebuild_player_ranks()

    await interaction.response.send_message(f'{member1_name}さん（戦力: {member1_power}）と{member2_name}さん（戦力: {member2_power}）の戦力値を交換しました。')

@bot.tree.command(name='exclude_member', description='グループ自動選出から除外するメンバーを設定します。')
@app_commands.describe(member_names='除外するメンバーの名前 (スペース区切り)')
async def exclude_member(interaction: discord.Interaction, member_names: str):
    """
    Sets one or more members to be excluded from auto group selection.
    Note: Autocomplete is not supported for space-separated arguments.
    """
    user_id = interaction.user.id
    if user_id not in excluded_members:
        excluded_members[user_id] = []

    added_members = []
    not_found_members = []
    
    names_list = member_names.split()
    
    for member_name in names_list:
        if member_name not in [p['name'] for p in OVERALL_RANKS]:
            not_found_members.append(member_name)
        elif member_name in excluded_members[user_id]:
            # Ignore members who are already in the exclusion list
            pass
        else:
            excluded_members[user_id].append(member_name)
            added_members.append(member_name)
    
    message = ''
    if added_members:
        message += f'`{", ".join(added_members)}`さんを自動選出から除外しました。\n'
    
    if not_found_members:
        message += f'⚠️ 登録されていないメンバー: `{", ".join(not_found_members)}`'
    
    if not message:
        message = '指定されたメンバーはすべてすでに除外リストにいます。'
        
    await interaction.response.send_message(message)

@bot.tree.command(name='clear_excluded', description='自動選出の除外メンバーリストをリセットします。')
async def clear_excluded(interaction: discord.Interaction):
    """
    Resets the list of excluded members.
    """
    user_id = interaction.user.id
    if user_id in excluded_members:
        excluded_members[user_id] = []
        await interaction.response.send_message('除外メンバーリストをリセットしました。すべてのメンバーが自動選出の対象になりました。')
    else:
        await interaction.response.send_message('除外メンバーリストはすでに空です。')
        
# New: Command to fix a team
@bot.tree.command(name='fix_team', description='指定したメンバーをチームに固定し、特定のメンバーを優先的に追加します。')
@app_commands.describe(fixed_names='チームに固定するメンバーの名前 (スペース区切り)', preferred_names='固定チームに優先的に追加するメンバーの名前 (スペース区切り)')
async def fix_team(interaction: discord.Interaction, fixed_names: str, preferred_names: str = None):
    """
    Sets one or more members to be "fixed" in a team, with optional preferred members.
    """
    user_id = interaction.user.id
    if user_id not in fixed_teams:
        fixed_teams[user_id] = []
    if user_id not in preferred_members:
        preferred_members[user_id] = []

    added_fixed = []
    not_found_fixed = []
    fixed_list = fixed_names.split()
    
    # Process fixed members
    for name in fixed_list:
        if name not in [p['name'] for p in OVERALL_RANKS]:
            not_found_fixed.append(name)
        elif name in fixed_teams[user_id]:
            pass
        else:
            fixed_teams[user_id].append(name)
            added_fixed.append(name)
            
    message = ''
    if added_fixed:
        message += f'`{", ".join(added_fixed)}`さんをチームに固定しました。\n'
    
    if not_found_fixed:
        message += f'⚠️ 登録されていない固定メンバー: `{", ".join(not_found_fixed)}`\n'
    
    # Process preferred members if provided
    if preferred_names:
        added_preferred = []
        not_found_preferred = []
        preferred_list = preferred_names.split()
        for name in preferred_list:
            if name not in [p['name'] for p in OVERALL_RANKS]:
                not_found_preferred.append(name)
            elif name in preferred_members[user_id]:
                pass
            else:
                preferred_members[user_id].append(name)
                added_preferred.append(name)
        
        if added_preferred:
            message += f'`{", ".join(added_preferred)}`さんを固定チームに優先的に追加するように設定しました。\n'
        if not_found_preferred:
            message += f'⚠️ 登録されていない優先メンバー: `{", ".join(not_found_preferred)}`'
    
    if not message:
        message = '指定されたメンバーはすべてすでにチームに固定または優先設定されています。'
        
    await interaction.response.send_message(message)

# New: Command to clear fixed team list
@bot.tree.command(name='clear_fixed', description='チーム固定メンバーと優先メンバーリストをリセットします。')
async def clear_fixed(interaction: discord.Interaction):
    """
    Resets the list of fixed members.
    """
    user_id = interaction.user.id
    if user_id in fixed_teams:
        fixed_teams[user_id] = []
    if user_id in preferred_members:
        preferred_members[user_id] = []
    
    await interaction.response.send_message('チーム固定メンバーと優先メンバーリストをリセットしました。')

@bot.tree.command(name='check_available', description='グループ編成に参加可能なメンバー数を確認します。')
async def check_available(interaction: discord.Interaction):
    """
    Displays the total number of members available for group formation.
    """
    user_id = interaction.user.id
    excluded_list = excluded_members.get(user_id, [])
    fixed_list = fixed_teams.get(user_id, [])
    preferred_list = preferred_members.get(user_id, [])
    
    # The set of all members involved in fixed/preferred teams
    fixed_and_preferred = set(fixed_list) | set(preferred_list)
    
    available_members = [
        p for p in OVERALL_RANKS
        if p['name'] not in excluded_list and p['name'] not in fixed_and_preferred
    ]
    
    total_involved = len(fixed_list) + len(preferred_list) + len(available_members)
    
    await interaction.response.send_message(
        f'現在、グループ編成に参加可能なメンバーは**{len(available_members)}人**です。\n'
        f'(固定メンバーと優先メンバーは含まれません)'
    )


@bot.tree.command(name='auto_create_group', description='自動的にメンバーを選出し、指定されたタイプのグループを作成します。')
@app_commands.describe(
    group_type='グループのタイプ: balance, high_power, carry (デフォルトはbalance)',
    probability='固定チームに優先メンバーが追加される確率 (0.0 から 1.0 の間, デフォルトは 1.0)'
)
async def auto_create_group(interaction: discord.Interaction, group_type: str = 'balance', probability: float = 1.0):
    """
    Automatically forms groups of the specified type.
    Available types: 'balance', 'high_power', 'carry'
    """
    print("--- Debug Log: auto_create_group command started ---")
    await interaction.response.defer()
    
    user_id = interaction.user.id
    excluded_list = excluded_members.get(user_id, [])
    carried_list = carried_members.get(user_id, [])
    fixed_list = fixed_teams.get(user_id, [])
    preferred_list = preferred_members.get(user_id, [])

    print(f"User ID: {user_id}")
    print(f"Exclusion List: {excluded_list}")
    print(f"Carried List: {carried_list}")
    print(f"Fixed Team List: {fixed_list}")
    print(f"Preferred Members List: {preferred_list}")
    print(f"Probability: {probability}")
    
    # Step 1: Initialize lists for team formation
    fixed_members = [p for p in OVERALL_RANKS if p['name'] in fixed_list]
    preferred_for_team1 = [p for p in OVERALL_RANKS if p['name'] in preferred_list]
    
    # Separate the members based on probability
    team1_members = fixed_members[:]
    other_members = []
    
    for member in preferred_for_team1:
        if random.random() < probability:
            team1_members.append(member)
        else:
            other_members.append(member)
            
    # Step 2: Filter available members, excluding those already processed
    processed_members_names = set(fixed_list) | set(preferred_list)
    available_members = [
        p for p in OVERALL_RANKS
        if p['name'] not in excluded_list and p['name'] not in processed_members_names
    ]
    
    # Add the "other" members from the preferred list to the available members
    available_members.extend(other_members)
    
    # Shuffle the available members to ensure randomness
    random.shuffle(available_members)
    
    num_total_members = len(team1_members) + len(available_members)
    print(f"Number of total members: {num_total_members}")
    
    # Check for a minimum of 4 members
    if num_total_members < 4 and len(team1_members) < 4:
        print("Warning: Less than 4 members available.")
        await interaction.followup.send(
            f'⚠️ グループを作成するには最低4人のメンバーが必要です。現在参加可能なメンバーは**{num_total_members}人**です。'
            f'\n`/member_list`コマンドでメンバーを確認してください。'
        )
        print("--- Debug Log: Command finished (warning) ---")
        return

    final_teams = []
    message_header = ''

    # Add the probabilistic fixed team first
    if team1_members:
        final_teams.append(team1_members)

    # Force "carry" type if carried members are set
    if carried_list and group_type != 'carry':
        await interaction.followup.send(f'キャリー対象が設定されているため、グループタイプを`carry`に強制設定します。')
        group_type = 'carry'

    if group_type == 'carry':
        print("Group Type: Carry")
        message_header = '**🤖 自動グループ編成結果 (キャリー型)**\n\n'
        if not carried_list:
            print("Error: Carried list is empty.")
            await interaction.followup.send('キャリー型グループを作成するには、`/set_carried`でキャリー対象を設定するか、`/auto_create_group carry`と指定してください。')
            print("--- Debug Log: Command finished (error) ---")
            return

        # Find carried member in available members
        carried_member = next((m for m in available_members if m['name'] == carried_list[0]), None)

        if not carried_member:
            print(f"Error: Carried member '{carried_list[0]}' not found in available members.")
            await interaction.followup.send(f'指定されたキャリーメンバー `{carried_list[0]}` が参加可能メンバーリストに見つかりませんでした。')
            print("--- Debug Log: Command finished (error) ---")
            return

        remaining_members = [m for m in available_members if m['name'] != carried_list[0]]
        remaining_members.sort(key=lambda x: x['power'], reverse=True)

        if len(remaining_members) < 3:
            print(f"Warning: Less than 3 remaining members. Count: {len(remaining_members)}")
            await interaction.followup.send(f'キャリーチームを編成するには、{len(remaining_members)}人ではメンバーが不足しています。')
            print("--- Debug Log: Command finished (warning) ---")
            return

        # Randomly select 3 players from the top 10 power players
        top_players_pool = remaining_members[:10]
        if len(top_players_pool) < 3:
            top_3_members = top_players_pool
        else:
            top_3_members = random.sample(top_players_pool, 3)

        # Exclude the selected members from the remaining members
        remaining_members_for_balance = [m for m in remaining_members if m not in top_3_members]
        
        # Add the carry team to the final list
        final_teams.append([carried_member] + top_3_members)
        
        # Form balanced teams with the remaining members
        teams_balance = create_balanced_teams(remaining_members_for_balance)
        final_teams.extend(teams_balance)
        
    elif group_type == 'balance':
        print("Group Type: Balance")
        message_header = '**🤖 自動グループ編成結果 (バランス型)**\n\n'
        teams_balance = create_balanced_teams(available_members)
        final_teams.extend(teams_balance)
        
    elif group_type == 'high_power':
        print("Group Type: High Power")
        message_header = '**🤖 自動グループ編成結果 (高戦力型)**\n\n'
        teams_high_power = create_high_power_teams(available_members)
        final_teams.extend(teams_high_power)
        
    else:
        await interaction.followup.send(f'無効なグループタイプです。`balance`, `high_power`, `carry`から選択してください。')
        print("--- Debug Log: Command finished (invalid type) ---")
        return

    # Select a leader for each team
    teams_with_leader = []
    for team in final_teams:
        leader = None
        leader_candidates_in_team = [m for m in team if m['name'] in LEADER_CANDIDATES]
        if leader_candidates_in_team:
            leader = max(leader_candidates_in_team, key=lambda x: x['power'])
        
        team_members_without_leader = [m for m in team if m['name'] != (leader['name'] if leader else '')]
        
        teams_with_leader.append({
            'members': team_members_without_leader,
            'leader': leader
        })

    # Display results
    if not teams_with_leader:
        print("Warning: Failed to form groups.")
        await interaction.followup.send("グループを編成できませんでした。")
        print("--- Debug Log: Command finished (formation failed) ---")
        return

    message = message_header
    for i, team_data in enumerate(teams_with_leader):
        leader = team_data['leader']
        members = team_data['members']
        
        members_list = members[:]
        if leader:
            members_list.append(leader)
        
        team_power_total = sum(m['power'] for m in members_list)
        members_str = ', '.join([f'{m["name"]} ({m["profession"]})' for m in members_list])

        # Check for teams with fewer than 4 members AFTER formation
        team_size_warning = ''
        if len(members_list) < 4:
            team_size_warning = '⚠️ **注意:** このチームは4人未満です。\n'
        
        # Check for the number of front-line members (Swordsman/Knight)
        front_liners_count = sum(1 for m in members_list if PROFESSIONS[m['profession']] == '前衛')
        warning_message = ''
        if front_liners_count == 0:
            warning_message = '⚠️ **注意:** このチームには前衛メンバー (剣士/騎士) がいません。\n'

        message += f'**=== チーム {i + 1} ===**\n'
        if leader:
            message += f'リーダー: **{leader["name"]}** ({leader["profession"]})\n'
        else:
            message += f'リーダー: **未決定**\n'
            message += '⚠️ **注意:** リーダー候補がいなかったためリーダーが自動設定されませんでした。\n'
        message += team_size_warning
        message += warning_message
        message += f'メンバー: {members_str}\n'
        message += f'合計戦力: **{team_power_total}**\n\n'
    
    await interaction.followup.send(message)
    print("--- Debug Log: Command finished successfully ---")

def create_balanced_teams(members):
    """
    Shuffles members randomly and distributes them evenly into teams.
    This creates teams with minimal power differences.
    """
    random.shuffle(members)
    num_teams = math.ceil(len(members) / 4)
    if num_teams == 0:
        return []
    teams = [[] for _ in range(num_teams)]
    
    for i, member in enumerate(members):
        teams[i % num_teams].append(member)
        
    return teams

def create_high_power_teams(members):
    """
    Sorts members by power and distributes them sequentially.
    This intentionally creates teams with large power differences (strong and weak teams).
    This logic contains no randomness.
    """
    members.sort(key=lambda x: x['power'], reverse=True)
    
    teams = [members[i:i + 4] for i in range(0, len(members), 4)]
    
    return teams
    

@bot.tree.command(name='add_leader_candidate', description='リーダー候補にメンバーを追加します。')
@app_commands.describe(member_names='追加するメンバーの名前 (スペース区切り)')
async def add_leader_candidate(interaction: discord.Interaction, member_names: str):
    """
    Adds one or more members to the list of leader candidates.
    Note: Autocomplete is not supported for space-separated arguments.
    """
    added_members = []
    not_found_members = []
    
    names_list = member_names.split()

    for member_name in names_list:
        if member_name not in [p['name'] for p in OVERALL_RANKS]:
            not_found_members.append(member_name)
        elif member_name in LEADER_CANDIDATES:
            pass
        else:
            LEADER_CANDIDATES.append(member_name)
            added_members.append(member_name)
    
    message = ''
    if added_members:
        message += f'`{", ".join(added_members)}`さんをリーダー候補に追加しました。\n'
    
    if not_found_members:
        message += f'⚠️ 登録されていないメンバー: `{", ".join(not_found_members)}`'

    if not message:
        message = '指定されたメンバーはすべてすでにリーダー候補です。'
    
    await interaction.response.send_message(message)

@bot.tree.command(name='remove_leader_candidate', description='リーダー候補からメンバーを削除します。')
@app_commands.describe(member_names='削除するメンバーの名前 (スペース区切り)')
async def remove_leader_candidate(interaction: discord.Interaction, member_names: str):
    """
    Removes one or more members from the list of leader candidates.
    Note: Autocomplete is not supported for space-separated arguments.
    """
    removed_members = []
    not_found_candidates = []
    
    names_list = member_names.split()

    for member_name in names_list:
        if member_name in LEADER_CANDIDATES:
            LEADER_CANDIDATES.remove(member_name)
            removed_members.append(member_name)
        else:
            not_found_candidates.append(member_name)

    message = ''
    if removed_members:
        message += f'`{", ".join(removed_members)}`さんをリーダー候補から削除しました。\n'
    
    if not_found_candidates:
        message += f'⚠️ リーダー候補リストに見つからなかったメンバー: `{", ".join(not_found_candidates)}`'

    if not message:
        message = '指定されたメンバーはすべてリーダー候補リストに見つかりませんでした。'

    await interaction.response.send_message(message)
        
@bot.tree.command(name='power_list', description='各職業の戦力ランキングを表示します。')
async def power_list(interaction: discord.Interaction):
    """
    Displays the overall power ranking and rankings by profession.
    """
    message = '**🏆 全体戦力ランキング**\n'
    sorted_overall_ranks = sorted(OVERALL_RANKS, key=lambda x: x['power'], reverse=True)
    for i, member in enumerate(sorted_overall_ranks):
        message += f'{i + 1}. {member["name"]}さん ({member["profession"]}): 戦力 {member["power"]}\n'

    message += '\n---**職業別ランキング**---\n\n'
    
    rebuild_player_ranks()

    for profession, ranks in PLAYER_RANKS.items():
        message += f'**{profession}**\n'
        for i, (name, power) in enumerate(ranks):
            message += f'{i + 1}. {name}さん: 戦力 {power}\n'
        message += '\n'
    await interaction.response.send_message(message)

# Flaskサーバーのインスタンスを作成
app = Flask(__name__)

# Botを起動する関数
def run_bot():
    """Function to start the Discord Bot"""
    if TOKEN is None:
        print("Error: DISCORD_TOKEN is not set in the .env file.")
    else:
        bot.run(TOKEN)

@app.route('/')
def home():
    return "Discord Bot is running!"

# Flaskサーバーを起動する関数
def run_flask():
    """Function to start the Flask server"""
    port = int(os.environ.get("PORT", 5000))
    # RenderはGunicornを使用するため、ここでは単純なapp.run()を使用します。
    # Gunicornの起動コマンドは別途Renderの設定で指定します。
    pass

if __name__ == '__main__':
    # Start the Flask server in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    # Start the bot in the main thread
    run_bot()