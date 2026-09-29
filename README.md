# Automação Industrial: Programação de CLP (IEC 61131-3), Controle PID 4–20 mA, USCA/QTA e Supervisório SCADA Modbus

Repositório de engenharia de automação industrial contendo programas de **Controladores Lógicos Programáveis (CLP)** segundo a norma **IEC 61131-3** (*Structured Text - ST* e *PLCopen XML* compatível com **CODESYS, Siemens TIA Portal, Rockwell Studio 5000 e WEG**), mapeamento de registradores **Modbus TCP/RTU** e motor de simulação em tempo real com **testes automatizados**.

## Módulos Implementados
1. **`FB_QTA_Controller.st` (USCA / Quadro de Transferência Automática 250 kVA):**
   - Máquina de estados finitos completa para transferência automática Rede (`52-R`) ↔ Grupo Moto-Gerador (`52-G`).
   - Supervisão trifásica de subtensão/sobretensão e frequência (ANSI 27/59/81), temporizador de confirmação de falta de rede (3 s), até 3 tentativas de partida (*cranking*), rampa de aquecimento (*warm-up*), retransferência temporizada (15 s) e resfriamento do motor diesel (*cooldown* de 30 s).
   - Intertravamento lógico e elétrico redundante garantindo exclusão mútua entre `52-R` e `52-G`.
2. **`FB_Level_PID_Controller.st` (Controle PID de Nível e Instrumentação 4–20 mA):**
   - Escalonamento de transmissores analógicos 4–20 mA (`LIT-101`) com diagnóstico de rompimento de cabo segundo a norma **NAMUR NE43** (`< 3,6 mA` ou `> 21,0 mA`).
   - Controlador PID discreto com *anti-windup* e intertravamento de segurança de nível alto-alto (`LSHH`) e baixo-baixo (`LSLL`).
3. **Exportação `PLCopen XML` (`src/plcopen_xml/Industrial_QTA_and_PID_PLC.xml`) e Diagramas elétricos QElectroTech / AutoCAD.**
