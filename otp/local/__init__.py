"""
In-process replacement for the Astron cluster.

Everything that astrond used to do for TTR-Offline (Message Director, State
Server, Database Server, DBSS, Client Agent and Event Logger) lives in this
package and runs inside the game process, on the same thread as the client,
the UberDOG and the AI. Repositories talk to it through in-memory datagram
queues (see LocalConnection) using the exact same Astron wire format they used
over TCP, so the game logic does not need to know the difference.
"""
