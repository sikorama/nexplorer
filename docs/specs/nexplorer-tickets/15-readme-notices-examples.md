Label: ready-for-agent

# 15: README, notices and examples

**What to build:** The repository is usable and correctly attributed by a newcomer. README (in English) explains what nexplorer is, how to launch it from a source checkout, how to connect a Next (`.sync5 -l` and the `nextsync.cfg` reminder). Third-party notices keep the MIT notice of code reused from ZX-Next-Unite and credit the NextSync protocol origin (Jari Komppa, Unlicense); HDFM-Gooey and hdfmonkey are not credited as dependencies. An `examples` folder holds the NextBASIC launcher programs supplied by the repository owner, which launch the dot in one command.

**Blocked by:** 02 (Tracer: connect and waiting screen)

**Status:** ready-for-agent

- [ ] README documents launch from source and connecting a Next
- [ ] Third-party notices carry the Unite MIT notice and the Jari Komppa / Unlicense credit
- [ ] `examples/` contains the owner's NextBASIC launcher programs (to be supplied by the owner; do not invent them)
- [ ] Everything is written in English



Je voudrais ajouter un tuto pour les gens qui commencent avec le next. L'idée est de mettre en place le nécessaire pour pouvoir utiliser l'outil

1/ Il faut configurer le wifi
2/ Il faut installer la commande dot .sync5 via gettit (on pourra profiter pour installer gettit2 si ce n'est déja fait)
3/ Le fichier sync doit etre déplacée  dans le répertoirte  c:/DOT
4/ Ensuite il faut lancer l'application python sur le PC, et sur le next `.sync -L <ip>`
5/ Pour simplifier l'utilisation, on pourr coppier le programme basic wrap-sync qui lance la commande .sync directement depuis le browser



