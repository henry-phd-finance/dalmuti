// 결정화(Determinization) 기법이 적용된 MCTS AI 로직

class MCTS_Pro_Node {
    /**
     * MCTS 트리의 각 노드를 나타냅니다.
     * @param {GameState} gameState - 이 노드의 게임 상태
     * @param {MCTS_Pro_Node} parent - 부모 노드
     * @param {object|string} move - 이 노드로 오게 만든 행동
     */
    constructor(gameState, parent = null, move = null) {
        this.gameState = gameState;
        this.parent = parent;
        this.move = move;
        this.children = [];
        this.wins = 0;
        this.visits = 0;
        this.unexploredMoves = this.gameState.get_possible_moves();
    }

    /**
     * UCB1 공식을 사용해 가장 유망한 자식 노드를 선택합니다. (Selection)
     */
    select_child() {
        const logTotalVisits = Math.log(this.visits);
        const ucbScore = (child) => {
            if (child.visits === 0) return Infinity;
            return (child.wins / child.visits) + 1.41 * Math.sqrt(logTotalVisits / child.visits);
        };
        return this.children.sort((a, b) => ucbScore(b) - ucbScore(a))[0];
    }

    /**
     * 아직 시도하지 않은 수를 사용해 자식 노드를 생성하고 트리를 확장합니다. (Expansion)
     */
    expand() {
        const move = this.unexploredMoves.pop();
        const nextState = this.gameState.make_move(move);
        const childNode = new MCTS_Pro_Node(nextState, this, move);
        this.children.push(childNode);
        return childNode;
    }

    /**
     * 시뮬레이션 결과를 자신과 모든 부모에게 전파합니다. (Backpropagation)
     */
    update(result) {
        this.visits += 1;
        this.wins += result;
        if (this.parent) {
            this.parent.update(result);
        }
    }
}

class MCTS_Pro_AI {
    constructor({ iterations = 1000 }) {
        this.iterations = iterations;
    }

    /**
     * --- 핵심 로직: 결정화(Determinization) ---
     * 현재 상태를 바탕으로, 상대방의 패를 무작위로 채운 '가상 세계'를 생성합니다.
     * @param {GameState} currentState - 현재의 실제 게임 상태
     * @returns {GameState} - 상대방의 패가 채워진 새로운 가상 게임 상태
     */
    _create_determinized_state(currentState) {
        const determinizedState = currentState.clone();
        const rootPlayerIndex = currentState.turnIndex;
        const myHand = currentState.players[rootPlayerIndex].hand;
        const tableCards = currentState.tableCards.cards;

        // 1. 전체 덱에서 '알려진 카드'(내 패, 테이블 위 카드)를 모두 제거하여 '미지의 카드' 풀을 만듭니다.
        const fullDeck = [];
        for (let i = 1; i <= 12; i++) { for (let j = 0; j < i; j++) fullDeck.push(i); }
        fullDeck.push(13, 13);

        const knownCards = [...myHand, ...tableCards];
        const unknownCardPool = fullDeck.filter(card => {
            const index = knownCards.indexOf(card);
            if (index > -1) {
                knownCards.splice(index, 1);
                return false;
            }
            return true;
        });

        // 2. '미지의 카드' 풀을 무작위로 섞습니다.
        for (let i = unknownCardPool.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [unknownCardPool[i], unknownCardPool[j]] = [unknownCardPool[j], unknownCardPool[i]];
        }

        // 3. 섞인 카드를 다른 플레이어들에게 실제 손패 장수에 맞게 나눠줍니다.
        let cardPoolIndex = 0;
        for (let i = 0; i < determinizedState.numPlayers; i++) {
            if (i !== rootPlayerIndex) {
                const otherPlayer = determinizedState.players[i];
                const handSize = otherPlayer.hand.length; // 실제 손패 장수
                otherPlayer.hand = unknownCardPool.slice(cardPoolIndex, cardPoolIndex + handSize);
                otherPlayer.sortHand();
                cardPoolIndex += handSize;
            }
        }
        
        return determinizedState;
    }

    find_best_move(initialState) {
        const rootNode = new MCTS_Pro_Node(initialState);
        const rootPlayerIndex = initialState.turnIndex;

        for (let i = 0; i < this.iterations; i++) {
            let node = rootNode;
            
            // 1. Selection & 2. Expansion
            while (node.unexploredMoves.length === 0 && node.children.length > 0) {
                node = node.select_child();
            }
            if (node.unexploredMoves.length > 0) {
                node = node.expand();
            }

            // 3. Determinization
            const determinizedState = this._create_determinized_state(node.gameState);

            // 4. Simulation (Rollout)
            let simState = determinizedState;
            while (!simState.gameOver) {
                const moves = simState.get_possible_moves();
                const randomMove = moves[Math.floor(Math.random() * moves.length)];
                simState = simState.make_move(randomMove);
            }

            // 5. Backpropagation
            const result = simState.winnerIndex === rootPlayerIndex ? 1 : 0;
            node.update(result);
        }

        if (rootNode.children.length === 0) return "pass";
        const bestChild = rootNode.children.sort((a, b) => b.visits - a.visits)[0];
        return bestChild.move;
    }
}
