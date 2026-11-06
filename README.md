# Estudos acadêmicos de automação industrial

Este repositório reúne exemplos de lógica para CLP e supervisão: blocos em Structured Text para transferência rede/gerador e controle PID de nível, um simulador discreto em Python e um mapa de registradores Modbus.

## Arquivos

- `src/iec61131/`: exemplos de lógica em Structured Text;
- `src/scada_modbus/`: simulador em Python e mapa Modbus;
- `src/plcopen_xml/`: arquivo de intercâmbio PLCopen XML;
- `src/qelectrotech/`: desenho de referência do painel;
- `tests/`: testes do simulador Python.

## Escopo e limites

O XML não foi importado e compilado em uma IDE de fabricante. O simulador Python representa passos discretos e não é um soft-PLC nem uma validação em tempo real. Não há ensaios com CLP, GMG ou quadro físico. Intertravamentos, proteções e segurança precisam de projeto e validação próprios antes de qualquer aplicação real. O desenho QElectroTech também deve ser tratado como referência em desenvolvimento.
