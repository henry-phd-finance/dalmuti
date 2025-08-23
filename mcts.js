// MCTS(몬테카를로 트리 탐색) 알고리즘의 핵심 로직

class MCTS_Node {
    /**
     * MCTS 트리의 각 노드를 나타냅니다.
     * @param {GameState} gameState - 이 노드의 게임 상태
     * @param {MCTS_Node} parent - 부모 노드
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
        const childNode = new MCTS_Node(nextState, this, move);
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
class MCTS_AI {
    /**
     * MCTS 알고리즘을 실행하여 최선의 수를 찾습니다.
     * @param {number} iterations - AI가 생각하는 깊이(시뮬레이션 반복 횟수)
     */
    constructor({ iterations = 1000 }) {
        this.iterations = iterations;
    }

    find_best_move(initialState) {
        const player = initialState.getCurrentPlayer();
        const tableCardsCount = initialState.tableCards.cards.length;

        // --- 핵심 최적화 1: 낼 카드 장수보다 내 패가 적으면 즉시 패스 ---
        if (tableCardsCount > 0 && player.hand.length < tableCardsCount) {
            console.log(`${player.name} (MCTS) auto-passes: Not enough cards.`);
            return "pass";
        }

        // --- 핵심 최적화 2: 상대가 '1' 카드를 냈다면 즉시 패스 ---
        if (tableCardsCount > 0 && initialState.tableCards.effectiveRank === 1) {
            console.log(`${player.name} (MCTS) auto-passes: Opponent played rank 1.`);
            return "pass";
        }

        // --- 기존 MCTS 로직 ---
        const rootNode = new MCTS_Node(initialState);
        const rootPlayerIndex = initialState.turnIndex;

        for (let i = 0; i < this.iterations; i++) {
            let node = rootNode;
            let state = initialState;

            // 1. Selection
            while (node.unexploredMoves.length === 0 && node.children.length > 0) {
                node = node.select_child();
                state = state.make_move(node.move);
            }

            // 2. Expansion
            if (node.unexploredMoves.length > 0) {
                node = node.expand();
                state = node.gameState;
            }

            // 3. Simulation (Rollout)
            let simState = state;
            while (!simState.gameOver) {
                const moves = simState.get_possible_moves();
                const randomMove = moves[Math.floor(Math.random() * moves.length)];
                simState = simState.make_move(randomMove);
            }

            // 4. Backpropagation
            const result = simState.winnerIndex === rootPlayerIndex ? 1 : 0; // 이겼으면 1, 졌으면 0
            node.update(result);
        }

        // 모든 시뮬레이션 후, 가장 많이 방문한(가장 안정적인) 수를 선택
        if (rootNode.children.length === 0) return "pass";
        const bestChild = rootNode.children.sort((a, b) => b.visits - a.visits)[0];
        return bestChild.move;
    }
}

class MCTS_PRO_AI {
    constructor({ iterations = 1000 }) {
        this.iterations = iterations;
    }

    _create_determinized_state(currentState) {
        const determinizedState = currentState.clone();
        const rootPlayerIndex = currentState.turnIndex;
        const myHand = currentState.players[rootPlayerIndex].hand;
        const tableCards = currentState.tableCards.cards;

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

        for (let i = unknownCardPool.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [unknownCardPool[i], unknownCardPool[j]] = [unknownCardPool[j], unknownCardPool[i]];
        }

        let cardPoolIndex = 0;
        for (let i = 0; i < determinizedState.numPlayers; i++) {
            if (i !== rootPlayerIndex) {
                const otherPlayer = determinizedState.players[i];
                const handSize = otherPlayer.hand.length;
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
            
            while (node.unexploredMoves.length === 0 && node.children.length > 0) {
                node = node.select_child();
            }
            if (node.unexploredMoves.length > 0) {
                node = node.expand();
            }

            const determinizedState = this._create_determinized_state(node.gameState);

            let simState = determinizedState;
            while (!simState.gameOver) {
                const moves = simState.get_possible_moves();
                const randomMove = moves[Math.floor(Math.random() * moves.length)];
                simState = simState.make_move(randomMove);
            }

            const result = simState.winnerIndex === rootPlayerIndex ? 1 : 0;
            node.update(result);
        }

        if (rootNode.children.length === 0) return "pass";
        const bestChild = rootNode.children.sort((a, b) => b.visits - a.visits)[0];
        return bestChild.move;
    }
}