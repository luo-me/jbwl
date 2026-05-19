from datetime import datetime

from .database import AgentRepo, BondRepo, TieRepo


class InferEngine:
    def __init__(self, db):
        self.db = db

    def infer_trust_transitivity(self, agent_a_id, agent_b_id, agent_c_id):
        bond_repo = BondRepo(self.db)
        tie_repo = TieRepo(self.db)

        bond_ab = bond_repo.get(agent_a_id, agent_b_id)
        if not bond_ab:
            return None
        tie_ab = tie_repo.get_by_bond_id(bond_ab.id)
        if not tie_ab:
            return None

        bond_bc = bond_repo.get(agent_b_id, agent_c_id)
        if not bond_bc:
            return None
        tie_bc = tie_repo.get_by_bond_id(bond_bc.id)
        if not tie_bc:
            return None

        if tie_ab.trust <= 0.5 or tie_bc.trust <= 0.5:
            return None

        indirect_trust = tie_ab.trust * tie_bc.trust * 0.5
        confidence = 0.3

        return {
            "agent_a_id": agent_a_id,
            "agent_c_id": agent_c_id,
            "inferred_trust": indirect_trust,
            "confidence": confidence,
            "method": "trust_transitivity",
        }

    def infer_by_observation(self, observer_id, agent_a_id, agent_b_id):
        bond_repo = BondRepo(self.db)
        tie_repo = TieRepo(self.db)

        bond_oa = bond_repo.get(observer_id, agent_a_id)
        if not bond_oa:
            return None
        tie_oa = tie_repo.get_by_bond_id(bond_oa.id)
        if not tie_oa:
            return None

        if tie_oa.trust <= 0.5:
            return None

        inferred_valence = tie_oa.valence * 0.3
        confidence = 0.2

        return {
            "agent_a_id": agent_a_id,
            "agent_b_id": agent_b_id,
            "inferred_valence": inferred_valence,
            "confidence": confidence,
            "method": "observation",
        }

    def infer_bond(self, requester_id, agent_a_id, agent_b_id):
        results = []

        bond_repo = BondRepo(self.db)
        bonds_from_a = bond_repo.list_by_agent(agent_a_id)
        for bond in bonds_from_a:
            if bond.source_agent_id == agent_a_id and bond.target_agent_id != agent_b_id:
                intermediate = bond.target_agent_id
                result = self.infer_trust_transitivity(agent_a_id, intermediate, agent_b_id)
                if result:
                    results.append(result)

        obs_result = self.infer_by_observation(requester_id, agent_a_id, agent_b_id)
        if obs_result:
            results.append(obs_result)

        if not results:
            return {
                "agent_a_id": agent_a_id,
                "agent_b_id": agent_b_id,
                "inferred": False,
                "method": None,
            }

        best = max(results, key=lambda r: r["confidence"])

        inferred_trust = best.get("inferred_trust", 0.0)
        inferred_valence = best.get("inferred_valence", 0.0)

        return self.create_inferred_bond(
            agent_a_id, agent_b_id,
            inferred_valence, inferred_trust,
            best["confidence"], best["method"],
        )

    def create_inferred_bond(self, source_agent_id, target_agent_id, inferred_valence, inferred_trust, confidence, method):
        bond_repo = BondRepo(self.db)
        tie_repo = TieRepo(self.db)

        existing_bond = bond_repo.get(source_agent_id, target_agent_id)
        if existing_bond:
            if not existing_bond.inferred:
                return {
                    "source_agent_id": source_agent_id,
                    "target_agent_id": target_agent_id,
                    "inferred": False,
                    "reason": "real_bond_exists",
                }

            existing_tie = tie_repo.get_by_bond_id(existing_bond.id)
            existing_valence = existing_tie.valence if existing_tie else 0.0
            existing_trust = existing_tie.trust if existing_tie else 0.0

            same_sign_valence = (existing_valence >= 0) == (inferred_valence >= 0)
            same_sign_trust = (existing_trust >= 0) == (inferred_trust >= 0)

            if same_sign_valence and same_sign_trust:
                new_confidence = min(existing_bond.confidence + 0.1, 0.8)
                self.db.conn.execute(
                    "UPDATE bonds SET confidence = ?, last_update = ? WHERE id = ?",
                    (new_confidence, datetime.now().isoformat(), existing_bond.id),
                )
                self.db.conn.commit()
            else:
                new_confidence = existing_bond.confidence - 0.2
                if new_confidence < 0.1:
                    bond_repo.delete(existing_bond.id)
                    return {
                        "source_agent_id": source_agent_id,
                        "target_agent_id": target_agent_id,
                        "inferred": False,
                        "reason": "confidence_below_threshold",
                    }

                if confidence > existing_bond.confidence:
                    tie_repo.update(existing_bond.id, valence=inferred_valence, trust=inferred_trust)

                self.db.conn.execute(
                    "UPDATE bonds SET confidence = ?, last_update = ? WHERE id = ?",
                    (new_confidence, datetime.now().isoformat(), existing_bond.id),
                )
                self.db.conn.commit()

            updated_bond = bond_repo.get_by_id(existing_bond.id)
            updated_tie = tie_repo.get_by_bond_id(existing_bond.id)
            return {
                "source_agent_id": source_agent_id,
                "target_agent_id": target_agent_id,
                "inferred": True,
                "confidence": updated_bond.confidence if updated_bond else new_confidence,
                "valence": updated_tie.valence if updated_tie else 0.0,
                "trust": updated_tie.trust if updated_tie else 0.0,
                "method": method,
            }

        new_bond = bond_repo.create(source_agent_id, target_agent_id, inferred=True, confidence=confidence)
        tie_repo.update(new_bond.id, valence=inferred_valence, trust=inferred_trust)
        new_tie = tie_repo.get_by_bond_id(new_bond.id)

        return {
            "source_agent_id": source_agent_id,
            "target_agent_id": target_agent_id,
            "inferred": True,
            "confidence": confidence,
            "valence": new_tie.valence if new_tie else inferred_valence,
            "trust": new_tie.trust if new_tie else inferred_trust,
            "method": method,
        }

    def get_agent_network(self, agent_id, depth=1):
        agent_repo = AgentRepo(self.db)
        bond_repo = BondRepo(self.db)
        tie_repo = TieRepo(self.db)

        nodes = {}
        edges = []

        center = agent_repo.get_by_id(agent_id)
        if center:
            nodes[center.id] = {"id": center.id, "name": center.name}

        direct_bonds = bond_repo.list_by_agent(agent_id)
        for bond in direct_bonds:
            source = agent_repo.get_by_id(bond.source_agent_id)
            target = agent_repo.get_by_id(bond.target_agent_id)
            if source and source.id not in nodes:
                nodes[source.id] = {"id": source.id, "name": source.name}
            if target and target.id not in nodes:
                nodes[target.id] = {"id": target.id, "name": target.name}

            tie = tie_repo.get_by_bond_id(bond.id)
            edges.append({
                "source": bond.source_agent_id,
                "target": bond.target_agent_id,
                "valence": tie.valence if tie else 0.0,
                "trust": tie.trust if tie else 0.0,
                "strength": tie.strength if tie else 0.0,
                "type": tie.type.value if tie else "stranger",
                "inferred": bond.inferred,
            })

        if depth >= 2:
            for bond in list(direct_bonds):
                neighbor_id = bond.target_agent_id if bond.source_agent_id == agent_id else bond.source_agent_id
                neighbor_bonds = bond_repo.list_by_agent(neighbor_id)
                for nb in neighbor_bonds:
                    n_source = agent_repo.get_by_id(nb.source_agent_id)
                    n_target = agent_repo.get_by_id(nb.target_agent_id)
                    if n_source and n_source.id not in nodes:
                        nodes[n_source.id] = {"id": n_source.id, "name": n_source.name}
                    if n_target and n_target.id not in nodes:
                        nodes[n_target.id] = {"id": n_target.id, "name": n_target.name}

                    edge_exists = any(
                        e["source"] == nb.source_agent_id and e["target"] == nb.target_agent_id
                        for e in edges
                    )
                    if not edge_exists:
                        tie = tie_repo.get_by_bond_id(nb.id)
                        edges.append({
                            "source": nb.source_agent_id,
                            "target": nb.target_agent_id,
                            "valence": tie.valence if tie else 0.0,
                            "trust": tie.trust if tie else 0.0,
                            "strength": tie.strength if tie else 0.0,
                            "type": tie.type.value if tie else "stranger",
                            "inferred": nb.inferred,
                        })

        return {
            "center": agent_id,
            "nodes": list(nodes.values()),
            "edges": edges,
        }
