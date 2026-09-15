from MODULOS.memory import memory_long
memory_long.inicializar_banco()
r = memory_long.buscar_historico_relevante("como esta o sistema de memoria")
print(f"Resultados encontrados: {len(r)}")
if r:
    print(f"Primeiro: [{r[0]['papel']}] {r[0]['mensagem'][:80]}")
else:
    print("(esperado: 0 no historico antigo sem ts_unix, funcionar para novas mensagens)")
    
# Simular uma conversa nova e ver se encontra
memory_long.registrar_conversa_global("user", "este e um teste de busca por cascata mensal")
r2 = memory_long.buscar_historico_relevante("cascata mensal teste")
print(f"\nApos salvar nova mensagem: {len(r2)} resultados")
if r2:
    print(f"Encontrado: {r2[0]['mensagem']}")
