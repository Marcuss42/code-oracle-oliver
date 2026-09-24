# Code Oracle — Oliver

Projeto de estudo pessoal desenvolvido para explorar a construção de um agente de IA especializado em **análise, compreensão e investigação de código-fonte**.

O agente é capaz de analisar repositórios, armazenar conhecimento sobre os arquivos analisados e utilizar esse conhecimento para responder perguntas técnicas sobre os projetos.

## 🔮 Oliver

**Oliver**, também conhecido como **Code Oracle**, é o agente responsável pela análise dos repositórios.

Oliver possui uma abordagem técnica, direta e orientada a evidências.

Ele pode:

* Analisar arquivos de código-fonte
* Analisar repositórios completos
* Continuar análises interrompidas
* Consultar conhecimento previamente armazenado
* Atualizar conhecimento previamente armazenado
* Investigar arquivos específicos
* Cruzar informações entre diferentes arquivos
* Cruzar informações entre diferentes repositórios
* Identificar relações entre componentes quando houver evidências
* Responder perguntas sobre a estrutura e implementação dos projetos
* Gerar relatórios sobre o conhecimento analisado

O objetivo é permitir que o usuário converse com seus próprios repositórios utilizando linguagem natural.

## 🧠 Conhecimento

O Code Oracle mantém conhecimento persistido sobre os arquivos analisados.

Esse conhecimento pode ser utilizado posteriormente para responder perguntas sem precisar analisar novamente todos os arquivos.

A estrutura de conhecimento é organizada por repositório e arquivo:

```text
conhecimento/
└── <repositorio>/
    └── arquivos/
        ├── arquivo1.java.json
        ├── arquivo2.py.json
        └── ...
```

O conhecimento armazenado funciona como uma fonte auxiliar.

O **código real possui prioridade** sobre qualquer análise armazenada ou resposta anterior.

Quando uma informação não puder ser determinada através do conhecimento disponível, Oliver pode consultar o código real do repositório.

## Repositórios

Oliver só pode analisar os repositórios definidos no arquivo:

```text
repos/repositorios.json
```

Esse arquivo define os repositórios disponíveis para análise e seus respectivos caminhos locais.

Exemplo:

```json
{
    "repositorios": [
        {
            "nome": "repositorio-a",
            "path": "C:/caminho/repositorio-a"
        },
        {
            "nome": "repositorio-b",
            "path": "C:/caminho/repositorio-b"
        }
    ]
}
```

Apenas os repositórios cadastrados nesse arquivo podem ser utilizados pelo agente.

## Arquitetura

O fluxo geral do agente pode ser representado como:

```text
                  Usuário
                     ↓
                  Oliver
                     ↓
              Modelo de IA
                     ↓
               Tool Calling
              ↙     ↓      ↘
       Conhecimento  Código  Repositórios
              ↓       ↓        ↓
          Análises   Arquivos  Git (Local)
              └───────┬────────┘
                      ↓
                  Resposta
```

O agente utiliza ferramentas para acessar as informações necessárias durante uma investigação.

Isso permite separar:

```text
Interpretação
     ↓
Decisão
     ↓
Consulta
     ↓
Análise
     ↓
Resposta
```

## Análise de repositórios

Durante uma análise geral, Oliver pode processar arquivos em lotes e registrar o conhecimento produzido.

Isso permite que uma análise extensa seja interrompida e posteriormente continuada, evitando a necessidade de começar novamente do zero.

Também é possível solicitar uma nova análise completa quando necessário.

Exemplo:

```text
Você: continue a análise do repositorio-a

Oliver:
[continua analisando os arquivos que ainda não possuem análise]
```

Ou:

```text
Você: analise tudo novamente
```

Nesse caso, o projeto pode ser analisado novamente independentemente do conhecimento existente.

## Exemplos de uso

### Perguntar sobre um projeto

```text
Você: como funciona o processamento de arquivos nesse projeto?
```

Oliver consulta o conhecimento disponível e, quando necessário, verifica o código real.

### Investigar um arquivo

```text
Você: o que o arquivo UserManger.java faz?
```

### Procurar uma implementação

```text
Você: onde é realizada a chamada para createUser?
```

### Cruzar informações

```text
Você: quais arquivos chamam esse serviço e o que acontece depois?
```

Quando houver evidências em diferentes arquivos, Oliver pode cruzar essas informações para construir a resposta.

### Consultar múltiplos repositórios

```text
Você: como o repositorio-b se relaciona com o repositorio-a?
```

A resposta deve ser baseada exclusivamente nas evidências encontradas nos repositórios.

## Comandos

O agente possui comandos para operações relacionadas ao conhecimento e análise dos repositórios.

Exemplos:

```text
analise tudo novamente
```

Refaz a análise completa de um repositório.

```text
continue a análise
```

Continua a análise dos arquivos ainda não processados.

```text
gere um relatório
```

Gera um relatório baseado no conhecimento disponível.

Além desses comandos, o agente pode receber perguntas normalmente em linguagem natural.

## Personalidade

Oliver possui uma personalidade **técnica, objetiva e direta**.

Seu comportamento é semelhante ao de um analista de código experiente:

* Vai diretamente ao ponto
* Prioriza evidências
* Evita explicações desnecessárias
* Não especula para preencher lacunas
* Diferencia fatos de inferências
* Aponta problemas diretamente quando existem evidências
* Utiliza o código como fonte principal da verdade

O objetivo não é simplesmente gerar respostas, mas **investigar o código e apresentar conclusões sustentadas por evidências**.

## Execução

O Code Oracle possui dois modos de execução.

### Terminal

Para executar o agente diretamente pelo terminal:

```powershell
python terminal.py
```

### Interface

Para executar o agente através da interface:

```powershell
python interface.py
```

Os dois modos utilizam o mesmo agente e as mesmas funcionalidades de análise e consulta.

## Tecnologias

* Python
* LLMs
* Tool Calling
* Git
* Análise automatizada de código
* Persistência de conhecimento
* JSON
* APIs de modelos de linguagem

## Objetivo do projeto

O Code Oracle foi desenvolvido como um projeto de **estudo pessoal e experimentação com agentes de IA aplicados à engenharia de software**.

O projeto explora conceitos como:

* Agentes de IA
* LLMs
* Tool Calling
* Análise automatizada de código
* RAG e conhecimento persistido
* Contexto de conversação
* Análise incremental
* Integração com Git
* Investigação de múltiplos repositórios
* Separação entre conhecimento armazenado e fonte de verdade
* Automação de tarefas relacionadas à análise de software

## 👤 Autor

**Marcus Paulo S. Francisco**

GitHub: **[@Marcuss42](https://github.com/Marcuss42)**

---

**Code Oracle — Oliver**

Um assistente para conversar sobre seus próprios códigos.
