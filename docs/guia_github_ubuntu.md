Guia de Referência Rápida do Git e GitHub

Este guia resume os comandos mais importantes para configurar, criar, e manter um repositório no GitHub a partir do terminal do Ubuntu.

1. Configuração Inicial (Feita apenas uma vez por computador)

Esses comandos configuram sua identidade no Git.

    sudo apt install git

        O que faz: Instala o Git no seu sistema Ubuntu.

    git config --global user.name "Seu Nome"

        O que faz: Define o nome de usuário que aparecerá como autor dos seus commits.

    git config --global user.email "seu-email@exemplo.com"

        O que faz: Define o e-mail que será associado aos seus commits. (Use o mesmo do seu GitHub).

2. Criando um Repositório Novo (Enviando uma pasta do PC para o GitHub)

Use este fluxo quando você já tem uma pasta de projeto no seu computador e quer criar um repositório novo no GitHub com ela.

    cd /caminho/para/sua/pasta

        O que faz: Navega até a pasta do seu projeto no terminal.

    git init

        O que faz: Inicia um repositório Git local na sua pasta. Cria uma subpasta oculta chamada .git para rastrear as mudanças.

    git remote add origin <URL_DO_SEU_REPOSITORIO.GIT>

        O que faz: Conecta seu repositório local a um repositório remoto (vazio) no GitHub. origin é o apelido padrão para essa conexão.

3. Fluxo de Trabalho Diário (O Ciclo Principal)

Estes são os comandos que você usará 99% do tempo para atualizar seu projeto.

    git status

        O que faz: O comando mais importante. Mostra o estado atual do seu repositório: quais arquivos foram modificados, quais são novos e o que está pronto para ser enviado.

    git add .

        O que faz: Adiciona todas as alterações atuais (arquivos novos e modificados) à "área de preparação" (staging area), preparando-os para o próximo commit.

        Alternativa: git add <nome_do_arquivo.py> para adicionar um arquivo específico.

    git commit -m "Sua mensagem de descrição"

        O que faz: "Salva" as alterações que estão na área de preparação como um ponto na história do projeto. A mensagem deve ser uma descrição clara do que foi feito nesta alteração.

    git push

        O que faz: Envia todos os seus commits (que estão salvos localmente) para o repositório remoto no GitHub (origin).

4. Marcando Versões Oficiais (Tags)

Use quando atingir um marco importante e quiser criar um "release" (Ex: Versão 1.0.0).

    git tag -a v1.0.0 -m "Descrição geral da versão"

        O que faz: Cria uma "etiqueta" ou "tag" permanente no commit mais recente, marcando-o como uma versão específica. A flag -a cria uma tag anotada, o que é uma boa prática.

    git push origin --tags

        O que faz: Envia especificamente as tags que você criou para o GitHub. O push normal não as envia.

5. Comandos Úteis (Solução de Problemas e Verificação)

Comandos que te ajudam a verificar o estado e a corrigir problemas comuns.

    git remote -v

        O que faz: Mostra a URL do repositório remoto ao qual seu projeto local está conectado. Útil para verificar se a conexão (origin) está correta.

    git remote set-url origin <NOVA_URL.GIT>

        O que faz: Altera a URL do repositório remoto origin, caso você tenha configurado errado ou o endereço tenha mudado.

    git branch -m main

        O que faz: Renomeia a branch atual para main. Útil para corrigir o problema de master vs main.

    git reset

        O que faz: "Limpa" a área de preparação. Desfaz um git add, tirando os arquivos da área de commit sem apagar nenhuma modificação no seu código.

    git pull

        O que faz: Baixa as atualizações mais recentes do repositório do GitHub e as mescla com seu trabalho local. Essencial se outra pessoa estiver trabalhando no mesmo projeto ou se você trabalha em mais de um PC.

    git log

        O que faz: Mostra o histórico de todos os commits feitos, com suas mensagens, autores e datas. 
 