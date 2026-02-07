# Portfolio Rebalancer

## Sobre este proyecto

Ante la disyuntiva de si hacer el proyecto a mano desde cero para demostrar que sé programar, me puse a pensar...

Al final del día, alguien que realmente quiere generar valor automatizando procesos sabe que para cosas chicas, **la IA es increíble para todo esto**. Además, igual después hay una instancia donde voy a tener que programar en vivo.

### El proceso

Primero (sabiendo que era un error) le dije a Claude que partiera el plan para iniciar el proyecto dadas las solicitudes del enunciado.

Sabía que era un error porque probablemente iba a armar algo inutil que tendría que cambiar después. Pero justo me había comprado el plan pago hace 2 días y tenía ganas de usarlo 😄

Mientras Claude trabajaba, le pregunté a ChatGPT:

> _"What are all the problems at the moment of making a portfolio balancing algorithm? I know that shares are not divisible, so it's never perfect"_

Para entender qué otras complejidades tiene un algoritmo de balanceo de portafolios.

### Decisiones de diseño

Claramente, vi que esto es un proyecto que puede ser **de semanas fácilmente**. No sabía si irme más por el lado matemático/algorítmico, o la parte de dejarlo más integrado/bonito. Me gustaban los dos.

Por lo que decidí acotarlo y enfocarme en:

**✅ Incluidos en el proyecto:**

- 🔹 **Indivisible assets** - Implementación con optimizador para manejar que las acciones no se pueden comprar en fracciones
- 🔹 **Capital constraints** - Rango de tolerancia del 1%-3% para permitir cierta flexibilidad en el balance

**❌ Dejados fuera del alcance:**

- ❌ Costos de transacción
- ❌ Requerimientod de mantener un capital minimo

Y por el lado de hacerlo interactivo

- Poder cargar los portafolios de Fintual
- Que tenaga una función para "revolver" el portafolio y poder probarlo
- Que sea una applicación tipo CLI

---

# Fases de claude

Le pedí que arme la parte base, de clases, de stock y portafolio y que implementara el algoritmo más simple posible. Sin pedirselo creó los tests.
Luego le fui sumando partes e iba viendo como resultaban. En un inicio iba a scrappear Fintual para obtener los % actuales de cada portafolio, pero descubrí que los tenían mucho más comodos para ser cconsumidos.

Luego le pedi que obtuviera de los enlaces {cursor rellea aqui los enlaces} y que los pudiera cargar dejando por default risky norris.

Luego de eso, quería hacer una interfaz donde poder verlo. Ahí le pedi que creara un tipo de aplicación de consola para poder explorar.

Mientras la hacía, me puse a corregir cosas como funciones muy largas, y le pedi que sacara todos los comentarios y explicaciones ya que solo hacían el codigo más feo.

Al verlo me dicuenta que estaba obteniendo los datos mal. Tuvimos que iterar un par de veces para que los extrajera bien, y luego los presentara dinamicamente como quería.

Luego le pedi la parte matemática. Esta la dejé para el final porque sabía que tenía que revisarla de alguna forma. Ya que viendo como se equivocó en extraer datos. No puedo confirale matemática.

Finalmente terminé con está aplicación. Me entretuve mucho y creo que quedó de una forma entretenida para ver,
