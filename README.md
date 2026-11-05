# Automação Industrial: Programação de CLP (IEC 61131-3), Controle PID 4–20 mA, USCA/QTA e Supervisório SCADA Modbus

Repositório acadêmico de automação industrial com exemplos em Structured Text (ST), modelo de simulação em Python e mapa Modbus. O XML PLCopen incorpora agora o mesmo código ST, mas a importação/compilação em um fabricante de CLP ainda não foi verificada. QElectroTech contém folhas-modelo incompletas; não são diagramas multifilares finalizados.

## Módulos Implementados
1. **`FB_QTA_Controller.st` (USCA / Quadro de Transferência Automática 250 kVA):**
   - Máquina de estados finitos conceitual para transferência automática Rede (`52-R`) ↔ Grupo Moto-Gerador (`52-G`), com realimentação auxiliar e transição aberta.
   - Confirmação de falha da rede de 3 s, até 3 partidas de 5 s com repouso de 5 s, estabilização de 5 s, tempo morto de 1,5 s, retorno à rede após 120 s estáveis e arrefecimento sem carga por 180 s.
   - Intertravamento lógico e checagem de contatos auxiliares no modelo; o intertravamento físico e a proteção da máquina precisam existir e ser validados fora do software.
2. **`FB_Level_PID_Controller.st` (Controle PID de Nível e Instrumentação 4–20 mA):**
   - Escalonamento de transmissores analógicos 4–20 mA (`LIT-101`) com diagnóstico de rompimento de cabo segundo a norma **NAMUR NE43** (`< 3,6 mA` ou `> 21,0 mA`).
   - Controlador PID discreto com limitação integral e bloqueio de nível alto-alto (`LSHH`). Não usa um `LSLL` no tanque de descarga; a condição de sucção/fonte requer entrada e definição próprias.
3. **Intercâmbio `PLCopen XML` (`src/plcopen_xml/Industrial_QTA_and_PID_PLC.xml`)** com fonte ST embutida e um esboço de folhas QElectroTech ainda não concluído.

## Limites

O motor Python representa uma simulação discreta; não é um soft-PLC nem valida tempo real. Não há hardware no ciclo, ensaios com GMG, certificação de segurança, integração Modbus de campo nem importação/compilação confirmada do XML em IDE de fabricante. O seletor de modo manual e rotinas de teste de carga também não estão implementados.
