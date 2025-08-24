import json
import time
from collections import Counter

# 우리가 만든 게임 로직과 AI들을 가져옵니다.
from dalmuti_game import GameState
try:
    from mcts_pro import MCTS_Pro_AI
except ImportError:
    print("WARNING: mcts_pro.py not found. MCTS_PRO style will not be available.")
    MCTS_Pro_AI = None

# --- 시뮬레이션 설정 ---
PLAYER_COUNTS_TO_TEST = [4, 5, 6, 7]  # 테스트할 플레이어 수
GAMES_PER_SETUP = 100               # 각 플레이어 수마다 반복할 게임 횟수 (10000은 매우 오래 걸립니다)
MCTS_ITERATIONS = 500               # AI의 생각 깊이 (200~500 정도가 적당합니다)
LOG_FILE_PATH = 'dalmuti_strategy_log.jsonl' # 로그가 저장될 파일 (.jsonl 형식)

def state_to_vector(state: GameState):
    """ 현재 게임 상태(State)를 머신러닝 모델이 이해할 수 있는 숫자 벡터로 변환합니다. """
    player_index = state.turn_index
    player = state.players[player_index]
    
    # 1. 내 손패 정보 (1~13번 카드 각 몇 장씩 있는지)
    my_hand_vector = [0] * 13
    for card in player.hand:
        my_hand_vector[card - 1] += 1
        
    # 2. 다른 플레이어들의 남은 카드 장수 (나를 기준으로 시계 방향 순서)
    other_players_hand_counts = [0] * (state.num_players - 1)
    for i in range(state.num_players - 1):
        other_index = (player_index + 1 + i) % state.num_players
        other_players_hand_counts[i] = len(state.players[other_index].hand)
        
    # 3. 테이블 정보 (놓인 카드의 등급, 장수)
    table_rank = state.table_cards.get('effective_rank', 0)
    table_count = len(state.table_cards.get('cards', []))
    table_vector = [table_rank, table_count]
    
    # 4. 라운드 정보 (이번 라운드에 패스한 사람 수)
    round_vector = [len(state.passed_in_round)]

    # --- 핵심 수정: 5. 현재까지 나온 모든 카드(버려진 카드) 정보 ---
    # 전체 덱의 카드 카운트를 미리 계산
    full_deck_counts = Counter([c for i in range(1, 13) for c in [i] * i] + [13, 13])
    
    # 현재 모든 플레이어의 손에 있는 카드를 계산
    all_hands_cards = []
    for p in state.players:
        all_hands_cards.extend(p.hand)
    all_hands_counts = Counter(all_hands_cards)

    # 전체 덱에서 현재 손패들을 빼면, 버려진 카드들의 목록이 나옴
    discard_pile_counts = full_deck_counts - all_hands_counts
    discard_vector = [discard_pile_counts.get(i, 0) for i in range(1, 14)] # 1~13번 카드 순서로 벡터 생성
    # --- 수정 종료 ---
    
    # 모든 정보를 하나의 긴 벡터로 합칩니다.
    return my_hand_vector + other_players_hand_counts + table_vector + round_vector + discard_vector

def action_to_dict(action):
    """ 행동(Action)을 저장 가능한 딕셔너리 형태로 변환합니다. """
    if action == "pass":
        return {"action_type": "pass"}
    return {"action_type": "play", "rank": action['rank'], "count": action['count']}

def run_simulation():
    if not MCTS_Pro_AI:
        print("MCTS_Pro_AI is not available. Please make sure mcts_pro.py is in the same folder.")
        return

    print("--- Dalmuti MCTS-Pro Strategy Simulation & Logging ---")
    
    # 로그 파일을 이어쓰기('a') 모드로 엽니다.
    with open(LOG_FILE_PATH, 'a') as f:
        for num_players in PLAYER_COUNTS_TO_TEST:
            print(f"\n--- Simulating for {num_players} players ---")
            
            # 모든 플레이어는 MCTS_PRO 스타일
            player_styles = ['mcts_pro'] * num_players
            mcts_ai = MCTS_Pro_AI(iterations=MCTS_ITERATIONS)
            
            for game_id in range(GAMES_PER_SETUP):
                state = GameState(player_styles)
                
                game_turns_data = [] # 이번 게임의 모든 턴 데이터를 임시 저장
                turn_number = 0

                while not state.game_over:
                    turn_number += 1
                    current_player_index = state.turn_index
                    
                    # 1. 행동 전 '상황' 기록
                    state_vector = state_to_vector(state)
                    
                    # 2. MCTS AI가 '행동' 결정
                    best_move = mcts_ai.find_best_move(initial_state=state)
                    
                    # 3. (상황, 행동) 데이터를 임시 저장
                    turn_data = {
                        "game_id": f"{num_players}p_{game_id}",
                        "turn_number": turn_number,
                        "player_index": current_player_index,
                        "state_vector": state_vector,
                        "action": action_to_dict(best_move)
                    }
                    game_turns_data.append(turn_data)

                    # 4. 결정된 행동으로 게임 진행
                    if best_move == "pass":
                        state.player_pass(state.turn_index)
                    else:
                        state.play_cards(state.turn_index, best_move['rank'], best_move['count'])

                # 5. 게임 종료 후, 모든 턴 데이터에 '결과' 추가
                winner_index = state.winner_index
                for turn_data in game_turns_data:
                    # 이 턴을 수행한 플레이어가 최종 승자인지 여부
                    turn_data['outcome_win'] = 1 if turn_data['player_index'] == winner_index else 0
                    
                    # 완성된 턴 데이터를 JSONL 형식으로 파일에 기록
                    f.write(json.dumps(turn_data) + '\n')
                
                print(f"  Game {game_id + 1}/{GAMES_PER_SETUP} finished. Winner: Player {winner_index + 1}")

    print(f"\nSimulation complete! All data saved to {LOG_FILE_PATH}")

if __name__ == '__main__':
    start_time = time.time()
    run_simulation()
    end_time = time.time()
    print(f"Total simulation time: {end_time - start_time:.2f} seconds.")
