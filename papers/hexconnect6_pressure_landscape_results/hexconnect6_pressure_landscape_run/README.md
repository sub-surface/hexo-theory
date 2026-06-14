# Hex Connect-6 exact transversal pressure landscape

This run computes the derived obligation hypergraph for every candidate two-stone move
in a finite axial/Eisenstein window, then computes exact hitting number tau by brute force.

Core definition:

    pressure(m) = max(0, tau(O(P,m)) - 2)

where O(P,m) is the family of urgent one- or two-cell obligations created by move m.

A positive pressure means that, in this derived local hypergraph game, a defender with
two stones cannot hit every urgent obligation in one reply.

See data/metrics.json and figures/.
