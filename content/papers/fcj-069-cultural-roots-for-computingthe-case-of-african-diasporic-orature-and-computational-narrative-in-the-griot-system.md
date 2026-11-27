---
fcj_id: FCJ-069
title: Cultural Roots for Computing:The Case of African Diasporic Orature and Computational Narrative in the GRIOT System
authors:
  - D. Fox Harrell
affiliation: Georgia Institute of Technology fox.harrell@lcc.gatech.edu
issue: 11
published: 2008-11-05
journal: The Fibreculture Journal
issn: 1449-1443
licence: CC BY-NC-ND
source_url: https://eleven.fibreculturejournal.org/fcj-069-cultural-roots-for-computingthe-case-of-african-diasporic-orature-and-computational-narrative-in-the-griot-system/
source_file: eleven.fibreculturejournal.org/fcj-069-cultural-roots-for-computingthe-case-of-african-diasporic-orature-and-computational-narrative-in-the-griot-system/index.html
---

### Introduction

> Folks. This here is the story of the Loop Garoo Kid. A cowboy so bad he made a working posse of spells phone in sick. A bullwhacker so unfeeling he left the print of winged mice on hides of crawling women. A desperado so ornery he made the Pope cry and the most powerful of cattlemen shed his head to the Executioner’s swine (Ishmael Reed, the opening to Yellow Back Radio Broke-Down,1969). {#para2}

Signifying, the African diasporic tradition of one-upmanship by verbally stringing together escalating oblique hyperboles, invigorates the passage above with its crescendo-ing description of ‘a bad man’. Signifying is but one important trope in African diasporic oral traditions, which often gains evocative power by employing oratory tropes (Gates Jr, 1988). In his essay ‘Oral Power and Europhone Glory’, author and theorist Ngugi wa Thiong’o (1998) identifies and elaborates a set of principles for analyzing oral systems of communication, and a perspective on the deployment of those principles in African diasporic contexts. He foregrounds an oral aesthetic system (to be explored later in this paper) including an account of conditions for performance, namely architectural space, time frame, an oral equivalent to mises-en-scène, and the audience-performer relationship. The elements of performance described by Ngugi are also central in many forms of computational narrative with its virtual worlds, procedurality, and user-machine interaction. This parallel fuels the realisation that computing technologies hold great potential for contributing to new forms of computational narrative expression beyond the privileged models typically encountered in discourse surrounding computational expressive practices; a broader view of narrative reveals diverse aesthetic traditions that contain well developed philosophies of interactivity and generativity that blend naturally with the expressive affordances of computational media. {#para3}

The use of particular privileged cultural models is currently entrenched in computing practice. However explicitly highlighting diverse cultural foundations is not a radical or revisionist gesture. I believe that it holds concrete advantages. This paper uses the case of computational narrative as exemplified by the GRIOT system to explore the importance of, and challenges involved in, explicitly grounding computing practices in culturally based values and practices. {#para4}

Section II elaborates upon the observation that cultural models are implicitly built into all computational systems, ranging from the structuring of basic hardware functionality, as in operating system design, to performing tasks usually thought of as human, as in artificial intelligence (AI) practices. {#para5}

Section III provides grounding remarks about the relationship of this paper’s central argument to controversies and crucial issues in socio-cultural theory, in particular avoiding typical pitfalls of essentialism, stereotyping, and cultural exploitation involved in explicitly culturally-based technical practices. {#para6}

Section IV details gains to be made by making the role of cultural values and practices in computing explicit using the relationship between African diasporic orature (traditions and systems of oral communication) and the GRIOT system as a case study. It articulates a view of African diasporic orature, primarily based upon that of Ngugi wa Thiong’o, that attempts to avoid the pitfalls of describing orature only in a binary oppositional relationship to literature, and the cultural prejudice that usually results from that dichotomy (Ngugi, 1998). This section also describes the functionality and structuring of the GRIOT system, some of its theoretical underpinnings, and five dimensions along which it reflects the view of African diasporic orature presented previously. {#para7}

In the conclusion, I discuss some of the challenges inherent in any broad discussion of cultural systems and a possible future direction for methodology useful for forwarding my argument. {#para8}

### I Cultural Foundations In Computing

Computing systems have developed within particular histories, communities of practice, conceptual metaphorical bases, and other dimensions of specific contexts. Consider the example of the ‘von Neumann architecture’, which refers to the type of stored-program architecture detailed by John von Neumann in his seminal work (von Neumann, 1945). Most contemporary references to this type of architecture elide its historical, material, and metaphorical origins. Von Neumann’s work was a profoundly mature articulation of an architecture type that persists in use to this day, but of course it arose in the context of its time. This can be seen easily by its initial proposed reliance upon the technological resources of its times. Von Neumann (1945) wrote ‘It is clear that a very high speed computing device should ideally have vacuum tube elements’. {#para9}

Of greater conceptual note, von Neumann’s metaphors have an unfamiliar ring to contemporary readers. Of the “central control part” of a computer, von Neumann (1945) wrote that ‘the logical control of the device … can be most efficiently carried out by a central control organ’. This usage of the biological term “organ” was not an isolated case of an incidental metaphor. In the parlance of his times, von Neumann wrote also of ‘memory organs’, ‘input and output organs’, and of information produced by ‘human actions being sensed by human organs’. The metaphorical mapping of a computer’s subunits to ‘organs’ has not persisted to this day. Von Neumann also claimed that ‘neurons of higher animals are definitely ‘elements’ such as those found in computing devices. While the analogy between computers and brains has persisted, for von Neumann (1945) it was a very literal analogy as he stated that the central arithmetical part, the central control part, and the memory ‘correspond to the associative neurons of the human nervous system’ and later he discussed the ‘equivalents’ to the sensory and motor neurons. Contemporary cognitive science has passed by the early McCulloch and Pitts model of the neuron first (indeed the cognitive linguistics enterprise within cognitive science has passed by the ‘brain is a computer’ metaphor) that von Neumann refers to, which at one time was seen as potentially powerful enough to model human neural functioning (McCullock and Pitts, 1942). {#para10}

The point of this discussion of von Neumann’s work is that even ubiquitous technical hardware innovations are deeply grounded within cultural and historical practices. These cultural-historical origins tend to exist implicitly within technologies as opposed to being articulated explicitly within technical or popular discourse. When technical work is conflated with philosophy, sciences studying the mind/brain complex, human languages, or related areas, the tangle of implicit cultural bases only becomes more challenging to precisely locate. {#para11}

Artificial intelligence (AI) and cognitive science are interdisciplinary fields with precisely the tangled heritage of traditions described above. The origins of these fields rest in a reification of the ‘brain is a computer’ metaphor as developed within engineering practice and (often empirical) scientific experimentation. However, the cultural and philosophical bases of these fields have been deeply criticised in (Agre, 1997; Dreyfus, 1992; Winograd and Flores, 1986) as being rooted in a particular tradition of thought, an important constituent of which is an interpretation of the philosophy of René Descartes. Describing the relationship between Cartesianism and computing in AI, Philip Agre (1997) writes: {#para12}

> …a powerful dynamic of mutual reinforcement took hold between the technology of computation and a Cartesian view of human nature, with computational processes inside computers corresponding to thought processes inside minds. But the founders of computational psychology, while mostly avowed Cartesians, actually transformed Descartes’s ideas in a complex and original way. … Their innovation lay in a subversive reinterpretation of Descartes’s original dualism. In The Passions of the Soul, Descartes had described the mind as an expressionless res cogitans [thinking thing] that simultaneously participated in and transcended physical reality. … Sequestered in this nether region with its problematic relationship to the physical world, the mind’s privileged object of contemplation was mathematics. {#para13}

Agre concludes his argument as follows: {#para14}

> … the founders of computational psychology nonetheless consciously adopted and reworked the broader framework of Descartes’s theory, starting with a single brilliant stroke. The mind does not simply contemplate mathematics, they asserted; the mind is itself mathematical, and the mathematics of the mind is precisely a technical specification for the causally explicable operation of the brain (Agre, 1997). {#para15}

The acceptance of the mind as being computational relies upon a set of assumptions that are based within a certain tradition. Recall that Descartes’ philosophy is intertwined with his theology. In Meditations on First Philosophy, for example, Descartes offers several philosophically based proofs of the existence of God (Descartes, 1996). It is not a far stretch to see the Cartesian foundations of AI and early cognitive science as a theological base for a type of computing practice. I make this stretch here to emphasise the point that implicit cultural beliefs, rooted in cultural traditions of thought, inform all of our technical practices. {#para16}

Similarly, in earlier work, Terry Winograd and Fernando Flores (1986) critiqued a type of rationalism held to be ‘the mainspring of Western science and technology’. Their critique of the rationalist tradition does not pit rationality against irrationality, but rather addresses a tradition that focuses on systematic and precise formulations of how valid reasoning is constituted. They argue that scientists often feel that a narrow rationalistic approach is seen as only opposed to ‘mysticism, religion, or fuzzy thinking that is a throwback to earlier stages of civilization’, a problematic worldview in that it omits its own implicit cultural origins, such as in the case of Cartesianism within the strand of computer science and cognitive science described above (Winograd and Flores, 1986). {#para17}

Here, I argue for the necessity of, within computing research and arts, critical thought about implicit cultural biases in computing (echoing Agre’s (1997) call for critical technical practices in Computational and Human Experience). Such critical thought can comprise bases for new technical and creative innovations. Overcoming such biases can enable computing to contribute to diverse cultural traditions, including that of African diasporic orature. {#para18}

### II Remarks on Essentialism, Stereotyping and Exploitation

Before discussing the primary content of this paper, I would like to ground the discussion with a few remarks to make my agenda and position clear. Any discussion of broad cultural traditions tends to generalise cultural phenomena, obliterate nuanced concern for the diversity within various traditions, and is ripe for criticism of the very notion of a ‘tradition’ itself. The concept of an African diasporic tradition of orature is problematic itself because of the extreme diversity of contexts and histories found within the diaspora, the interweaving of diverse culturally informed views that may or may not have contextual or historical relationships to practices and values of Africa, and the unique relationships to context and history that every individual in the diaspora may have. There are intersecting communities of practice with features that originated in particular specific African contexts, and that persist (often in quite transformed instantiations) in practices with African cultural origins or influences. I hope that the reader is aware of these and related issues, and sensitively regards the simplifications made in the argument here in service of the broader point that emphasises the explicit grounding of computing practices in culture. {#para19}

There are further issues related to discussion of cultural traditions that are imperative to raise. I do not want to suggest the ideal of a separate ‘African diasporic computing’, imputing technical practices with essentialist characteristics of ‘Africanness’. I also do not want to stereotype the aesthetic systems of particular cultures, perhaps implying, for example, that characteristics such as oral performance or integrative arts (discussed later in Section 4) are uniquely African, that African diasporic culture necessarily integrates metaphysical concerns with practical/productive concerns, or that cases of rationalism cannot arise in contexts other than those steeped in the ‘Western tradition’. Furthermore, I do not want the argument to be seen as enabling cultural plunder, i.e. using diverse aesthetic traditions only to empower privileged traditions within computing rather than enriching computing practices grounded in a plurality of worldviews. The following is a discussion of these issues. {#para20}

While discussing the relationship between African culture and technology in the West, and the confluence of these histories in the lived experience of the African diaspora, Ron Eglash notes that: {#para21}

Opposition to racism has often been composed through two totalizing, essentialist strategies: sameness and difference. For example, Mudimbe (1988) demonstrates how the category of a singular “African philosophy” has been primarily an invention of difference, having its creation in the play between “the beautiful myths of the ‘savage mind’ and the African ideological strategies of otherness.” In contrast, structuralists such as Levi-Strauss have attempted to prove that African conceptual systems are fundamentally the same as those of Europeans (both having their basis in arbitrary symbol systems) (Eglash, 1995). {#para22}

I reject the notion of an ‘African diasporic orature’ akin either to the ‘African philosophy’ disputed by Mudimbe or the structuralism of Levi-Strauss. Instead, I present a model rooted in traits of embodied performance and explicit subscription to a set of psychosocial/cultural values by some cultural producers. I believe that basing technical and creative production upon such explicit foundations can drive technical and artistic innovation. Such innovations will reflect the great individual variety of particular cultural productions, rooted in their contextual specificities, and drawing both explicitly and implicitly upon cultural resources ranging from culturally situated self-conception to adherence to large scale cultural narratives (even cultural narratives with dubious status such as Ong’s oral/written culture distinction (discussed later in Section 4), or the type of rationalistic perspective that Winograd and Flores critique) (Biakolo, 1999; Ong, 1982; Winograd and Flores, 1986). {#para23}

My aims coupled with the critique of ‘rationalistic’ models may suggest, for some, a binary opposition in which the cultures of the African diaspora are pitted against the oppressive imperial force of the Western tradition. While not ignorant of the historical, often colonial, circumstances from which both the monolithic and the simplified binary portraits arises, I oppose them both. Diverse traditions of orature have surely influenced my own computing practice, and many traits of orature are not restricted to any cultural tradition. My focus on African diasporic orature is motivated by the need for cultural specificity in order to make my points with precision, and the fact that African diasporic cultural traditions directly and explicitly influenced the development of the GRIOT system. In previous publications these influences have not been the focus of my presentation of the GRIOT system, and this may have had the residual effect that many aspects of the system have unfortunately heretofore been described primarily in terms privileged in computer science practices (Goguen and Harrell, 2004; Harrell, 2006). {#para24}

I believe that engaging in computing practices based explicitly in cultural traditions compels practitioners to critically examine what those traditions afford us. For example, knowledge is not neatly packaged into purely rational or purely mystical boxes. René Decartes and Isaac Newton both invoked forms of mysticism, yet their works also bear systematic components amenable to computational implementation and scientific investigation (Descartes, 1996; Dobbs, 1991). But my argument is not an appeal to mysticism. In explicitly culturally grounded computational practices we do not have to abandon rationality and appeal to intuition or mysticism. We must, however, acknowledge that some forms of knowledge are inherently not formal or computational, and that other forms of knowledge may be naturally amenable to formal representation and computational manipulation. For expressive computing practices, we can investigate the aesthetic and interpretive effects of computational structuring and algorithmic processing on cultural forms. Understanding that cultures contain many non-computational aspects, even mystical aspects, does not mean that we should abandon approaching serious humanistic issues within computational contexts. It also does not make the computer science ‘fuzzy’ by association. Instead, new possibilities can arise by engaging in careful, respectful dialogue between cultural traditions and computational practices when the affordances of the computational medium are seen as resources for culturally grounded development and implementation. {#para25}

Finally, the proposal here is not that computing practices should mine diverse forms of cultural production for new models that can inform development of new systems and creative practices to exist within an imaginary shared culture amongst technologically privileged practitioners and consumers. This point of view would posit cultures as ‘resources’ to be exploited by technical work. Instead, the proposal is that examination of diverse cultural practices and values can enrich our understandings of our computational practices, and that computational practices always are rooted in particular cultural values. I am only attempting to make explicit the ways in which culture can provide a lens with which to view our work, and that cultural views and values that are often not privileged within technical work may prove to be a valuable lens. {#para26}

### III Case Study of African Diasporic Orature and the GRIOT System

In this paper I focus upon the ways that privileged/dominant accounts of, implicit biases within, and incontrovertible traditions underlying computing practices exclude possibilities enabled by other traditions.It is the inverse of the model that proposes to export technologies to under(materially)resourced ‘third-world’ contexts as an humanistic gesture. I suggest that diverse cultural values and practices represent not merely resources for new possibilities within (implicitly Western) computing, but rather legitimate foundations for rigorous technical and/or artistically expressive computing practices. The accounts of African diasporic orature and the GRIOT system that follow reflect this focus. {#para27}

***African Diasporic Orature*** {#para28}

My view of orature is informed by a plurality of traditions within the African diaspora. Orature takes on particular importance in the African diasporic context because crucial bodies of knowledge, for example ontologies of ancestry, of deep cultural and religious significance in many diverse African cultures, have traditionally been transmitted orally. The cultural role of the griot, a West African praise singer and performer often serving the role of providing an account of genealogical ancestry, is an example of cultural infrastructure for maintaining such ontologies. This account has grossly simplified these issues, but hopefully has proved sufficient to motivate the specificity of the discussion of orature that follows. {#para29}

**Remarks on Orality** {#para30}

Walter Ong has presented a well known commentary on the dual modes of communication know as orality and literacy (Ong, .1982). He described speech as being fundamentally related to time, since it is apprehended primarily via our auditory faculty, and the written word as being primarily related to space, since it is apprehended primarily via our visual faculty. He differentiated the irredeemable nature of time, and therefore of oral utterances (except via memory), from the revisitable nature of space, and therefore of written signs (that are arrested in time). While Ong makes a sharp series of observations about the reliance of oral communication of memory and common traits of oral exposition such as repetition or contextual situatedness, his grander argument is a reductive one that exhibits a type of technological/linguistic determinism in which prevalence of either oral or written communication technologies and modes of communication within a culture combine to have a singular determining effect upon the nature knowledge and discourse within an entire culture. A thorough critique of Ong is presented by Emevwo Biakolo (1999), which illuminates ways in which the binary opposition between oral culture and written culture serves to preserve a system of cultural prejudice informed by a ‘faulty principle of causality’. Biakolo cites Ruth Finnegan to make this point: {#para31}

> Much of the plausibility of the ‘Great Divide’ theories has rested on the often unconscious assumption that what the essential shaping of society comes from is its communication technology. But once technological determinism is rejected or queried, then questions immediately arise about these influential classifications of human development into two major types: oral/primitive as against oral/literate … It is worth emphasizing that the conclusions from research, not only about the supposed ‘primitive mentality’ associated with orality, but also about, for example, concepts of individualism and the self, conflict and scepticism, or detached and abstract thought in non-literate cultures now look different … [and] once-confident assertions about the supposed differentiating features of oral and literate cultures are now exposed as decidedly shaky (Finnegan, 1988). {#para32}

Rather than reproducing Biakolo’s argument, and the prejudices inherent in Ong’s that it reveals, in this paper I focus on an account of African orature provided by Ngugi wa Thiong’o that does not rest upon the orality/literacy binary opposition (Ngugi, 1998). Ngugi does not essentialise African orature or engage in a narrow (implicitly hierarchically) comparative project as such. He begins with a comparative approach only to destabilise the hierarchy in which literacy is presented as privileged more than orality, and quickly moves to the matter of articulating a culturally situated view of oral aesthetic systems. Ngugi is informative here because he indeed focuses on the factors that come into play in ‘the actual execution’ of oral performance. For some cultural producers, it is the shared values of cultural participants that are taken as the primary aspects of a particular communication form, embodied performance (in the cognitive science sense of not only physical embodiment but also implication within contextualised social systems (Dourish, 2001) is seen as secondary. In this paper, the concept of African diasporic orature proposed by Ngugi is interpreted in this manner. For Ngugi, twin aspects of orature are the embodied aspects of its performance, and the fact of a commitment to a set of shared values in processes of cultural production. That is, adherence to a particular set of such values, that are often deployed through embodied oral performance (but need not be), can comprise a cultural form of production. Those particular values, however, are not essentially intrinsic to individuals forced into any particular cultural category, or to any one group of people or particular culture. It is a nuanced position, but one that helps to define a concept of African diasporic orature upon which cultural producers can explicitly build, but one that does not try to assert grand unifying themes that are necessarily and essentially exhibited by all cultural producers within the diaspora. {#para33}

**Ngugi wa Thiong’o’s Model of African Orature** {#para34}

The author Ngugi wa Thiong’o asserts that the term orature was ‘coined in the [Nineteen] Sixties by Pio Zirimu, the late Ugandan linguist’, and that the impetus for the coinage arose from two debates (Ngugi, 1998). The first regarded the elevated status of the English language and English departments in the>African>>Academy>. The second regarded the casting of ‘oral literature’ as folkloric and primitive or as the original basis of all textual composition (and that power relationships associating peasantry with illiteracy and the technological characteristic of the reproducibility of text were perhaps the root of its dominance). These debates arose to question the secondary role that oral tradition has come to occupy in relation to the literary traditions, while in many African societies oral traditions played a central role in knowledge representation, transmission, and expression. The central observation about this debate being made here is that orature need not stand in an hierarchical relationship to literature (Ngugi, 1998). {#para35}

The oral system is not a ‘pre-literate’ system, it is a different ‘formal narrative, dramatic, and poetic system’ ((Ngugi, 1998). This shift of perspective allow for the insight that media forms such as cinematic systems and computational narrative systems do not (in the words of Jay Bolter and Richard Grusin) simply ‘remediate’ older forms via ‘absorption’ (replacing old media with new), thereby rendering oral or textual into obsolete relics (Bolter and Grusin, 1999; Ngugi, 1998). Older media can also be said to be ‘hypermediated’ (refashioned while retaining attributes of its media heritage) by newer media (Bolter and Grusin, 1999). Under this view, it is not necessarily literary, or textual, media forms that comprise the remediated bases of computational media forms. Forms of orature may be the primary media forms that are remediated in some cases, and in such cases it is instructive to investigate the attributes of the influential traditions of orature. Ngugi suggests two characteristics of African diasporic orature that may persist and serve as foundations for interpreting “cyberspace” media forms (Ngugi uses ‘cyberspace’ as a blanket term for computational media involving spatial and social performance). These two characteristics are its (1) performative, and (2) integrative dimensions discussed respectively hereafter. {#para36}

Ngugi (1998) describes four conditions underlying the realisation of performative oral aesthetics in many African contexts. These are (1) architectural space, (2) time frame, (3) (oral) mises-en-scène, and (4) the audience-performer relationship. Descriptions of each of these conditions follow. The architectural space typically is an open space, and most often a circular space. The choice of a circle is not incidental, it has a symbolic unifying import within the traditions the Ngugi describes. Ngugi describes how time frame establishes the conditions for performance in several ways. Time frame can relate to the functionality of a particular performance, for example work songs being performed during work time or rite of passage performances coinciding with the necessary time of the ritual. The length of time also establishes conditions for performance. For Ngugi, ‘oral mises-en-scène’ refers to the different ambiences that can be created on the basis of costume, light source, etc. He writes ‘one can imagine the play of shadows and light on the bodies and costumes of the actors. The sources of light, whether fire, the moon, or the sun, could create different ambiences’ (Ngugi, 1998). Finally, the most important condition is the audience-performer relationship. Ngugi (1998) describes how the audience can play varying roles within performances, for example as critics or co-performers such as in stories ‘where a choral phrase or song or response’ is taken up by listeners who then become a part of the action. In such ‘real-time’ (live) performances, production and consumption dynamically intermingle. {#para37}

Ngugi’s description of the integrative characteristic of orature comprises a more delicate argument. This is because it arises from a view orature as a complete aesthetic system, reflecting adherence to a set of values shared among cultural participants. The conditions of oral performance are connected to the cultural beliefs, values, and contexts of its participants. This has already been seen in the example of dominance of the circle in architectural and performance spaces, with its symbolic and cosmological connotations. Ngugi (1998) comments that: {#para38}

> The interconnection between phenomena captured in the image of the circle, the central symbol of the African aesthetic, is consonant with the materialist metaphysics that one finds in so much of the pre-colonial African societies, the remnants of which still condition the African world-view. {#para39}

The point here is not the essentialisation of the ‘African world-view’, but rather that in performances based in such world-views, the establishment of the conditions for performance is not accomplished by happenstance or the stylistic innovation of a singular author. As an example, Ngugi notes that many pre-colonial Kenyan oral narratives reflect ‘the interdependence of forms of life in the fluidity of movement of characters through all the four realms of being and their interactions in flexible time and space. Plants, animals, and humans interact freely in many of the narratives’ (Ngugi, 1998). Thus, for cultural practitioners subscribing to such values, orature is a ‘complete aesthetic system’ in the sense that that the content of an oral performance, the material and social conditions of the performance, and the world-view informing the choice of content and conditions, are all integrated. This is one sense in which, within a shared cultural interpretation, African diasporic orature can be said to be integrative. {#para40}

Another sense in which Ngugi describes this culturally situated model of orature as being integrative is its rejection of formal boundaries of media and conventional artistic form – it allows for the integration of diverse art forms. This sense of the integrative character of orature potentially separates it from its roots in oral communication. Under this view, underlying cultural aspects of the aesthetic system are deployed through the conditions and form of the performance, but do not rely upon them. Indeed, by cultural participants, these cultural beliefs, values, and contexts may be seen as more intrinsic to the aesthetic form than even the fact of its oral transmission. If a particular form of expression is rooted in traditional aesthetic systems that are in turn rooted in an oral performance, then that form of expression can be seen as grounded in orature. {#para41}

This argument takes on life in a case Ngugi raises regarding the black arts movement in>Britain> around 1988, the author Kwesi Owusu invokes this integrative perspective as he writes: {#para42}

> Many black artists work in various media simultaneously, forging creative links, collaborations and alliances. This state of consciousness, a reflection of African and Asian attitudes to creativity, is what is called orature (Owusu, 1988). {#para43}

This essentialises and romanticises African and Asian cultural traditions, but it is informative in that Owusu’s conceptualisation hinges on the idea of orature as an integrated aesthetic system, and that particular oratory expressions can take shape in various eventual forms. Understood this way, orature becomes something like a communal and improvisational stance toward art. The term ‘orature’ becomes incredibly expansive, but not vacuous, under such an interpretation. {#para44}

This view of orature is informative in performance cases where there exist cultural traits originating in unique African contexts, but are deployed in diverse contemporary (often post-colonial) diasporic contexts. In such cases, the material conditions of performance may be radically transformed, for example the original architectural spaces, musical instruments, costumes, etc. may be unavailable. Furthermore, the cultural situations of participants may be radically transformed, for example they may speak colonial languages or may even be unaware of the traditions upon which the performance is based. The performance may also exist as an amalgam of various performance traditions, or include written, cinematic, or computational aspects. In such cases, orature provides a lens with which to examine cultural continuities within content, world-view, and media usage. In this paper I focus on continuities of media usage. The traits of orature mentioned here are not exclusive to African diasporic modes of expression, indeed Ngugi (1998) notes that Europhone theatre includes ‘mime, dance, masks, story-telling’, which features similar traits involving the conditions of performance. However, the performative and integrative characteristics of orature articulated by Ngugi present a frame that is based in careful reflection upon African diasporic cultural continuities, and that can undergird expressive computational practices as described below. {#para45}

> This argument, though atypical for a computer science practitioner to make, is no more exotic than finding roots of computational systems in Descartes’ view of the mathematical mind and transformations of that view. On the contrary, it is more explicit in its articulation of cultural influences, and carefully delineates the manner in which cultural practices and beliefs have influenced cultural production. In media theory there exists the notion of the computer as a ‘metamedium’, capable of reproducing other forms (but crucially featuring its own unique characteristics) (Manovich, 2001). I use the notion of African diasporic orature as a ‘metacultural’ concept, theorising an aesthetic system with clearly articulated media concerns (e.g. the four conditions for performance described above), but extending beyond oral performance to its hypermediated deployment using computational media. The GRIOT system, described below, is an implementation constructed within the tradition of computer science, but its areas of application have been greatly influenced by an explicit interest in (and implicit cultural world-view incorporating) the traits of African diasporic orature (Harrell, 2005a; 2005b). {#para46}

### IV The GRIOT System

GRIOT is a computer program developed as a platform for implementing interactive and generative computational narratives. The first systems built in GRIOT enable generation of poetry in response to user input. Joseph Goguen and I have coined the phrase ‘polymorphic poems’ or ‘polypoems’ to describe these works (Goguen and Harrell, 2004). A polypoem is not the individual output of one execution of GRIOT, but rather the code that generates a variety of poems algorithmically. An overview of the aims of the GRIOT system follows. {#para47}

The narrative computational media works created with GRIOT feature the following characteristics: generative content, semantics based interaction, reconfigurable narrative structure, and strong cognitive and socio-cultural grounding. {#para48}

Generative content means that a system can dynamically compose media content. The GRIOT system is an example of this. It has been used to implement computational poetry that generates new narrative poems with fixed themes but varying particular concepts upon each execution. This generativity is enabled by the Alloy system, which implements an algorithm that models key aspects of Gilles Fauconnier and Mark Turner’s (2002) theory of conceptual blending. Alloy is also the first implementation of Joseph Goguen’s algebraic semiotics approach to blending (Fauconnier and Turner, 2002; Goguen, 1998). {#para49}

Semantics based interaction means that (1) media is structured according to the meaning of its content, and (2) user interaction can affect content of a computational narrative in a way that produces new meanings that are constrained by the system’s author. ‘Meaning’ in this case means that the author has provided formal descriptions of domains and concepts pertinent to the media and subjective authorial intent. Reconfigurable narrative structure means the formal structure of a computational narrative can be dynamically restructured, either according to user interaction, or upon execution of the system as in the case of narrative generation. {#para50}

Strong cognitive and socio-cultural grounding here implies that despite the use of formal descriptions of semantic concepts, meaning is considered to be contextual, distributed among artifacts and through social interaction, and embodied. he formalizations used derive from and respect cognitive linguistics theories with such notions of meaning. In practice, a system author must be sensitive to these issues to effectively utilize the technical framework provided. Furthermore, the notion of narrative here is not biased toward one particular cultural model, the architecture is layered so that atop a technical layer a cultural producer can implement a range of structural narrative models. {#para51}

**The GRIOT Architecture** {#para52}

The following is a condensed description of GRIOT’s functionality. Technical details and a more elaborate description can be found in Goguen and Harrell (2006) and Harrell (2006). {#para53}

User input, in the form of keywords, is used to select the conceptual space network from a set of ontologies, called ‘theme domains’, that each contain sets of axioms about a particular theme. These axioms consist of binary relations between sorted constants. This conceptual space network, called an ‘input diagram’, consists of a generic space, two input spaces, and mappings from the generic space to each of the input spaces. The input diagram is passed as input to the ALLOY conceptual blending algorithm. ALLOY is the core component of GRIOT that is responsible for generating new content. An ‘output diagram’, consisting of a blended conceptual space and morphisms from the input spaces to the blended space, is output by ALLOY. Concepts are combined according to principles that produce ‘optimal’ blends. Typically this optimality results in ‘common sense’ blends, but for particular poetic effects different, ‘dis-optimal’ criteria can be utilised. ‘Phrase templates’, granular fragments of poetry organized by narrative clause type, are combined with the output of ALLOY (converted to natural language by mappings called ‘grammar morphisms’) to result in poems that differ not only in how the phrases are selected and configured, but in the meaning being expressed by the blended concepts. The phrases are said to be ‘instantiated’ when they are combined with the natural language representations of the blends by replacing ‘wildcards’ in the text. These wildcards are tokens representing where generated output can be incorporated, they also contain variables that specify how they are to be replaced, e.g. constraining the choice of theme domains, or selecting the lexical form to be mapped to by the grammar morphism. These templates are selected according to an automaton called an ‘Event Structure Machine’ (or ‘Narrative Structure Machine’), which also structures the reading of user input (Goguen and Harrell, 2006). {#para54}

Figure 1: The GRIOT System Architecture {#para55}

**GRIOT’s Basis in Orature** {#para56}

The Alloy algorithm central to GRIOT was, in part, conceived of as a critique of ‘good old fashioned’ symbolic, logic-based artificial intelligence approaches to meaning construction. The GRIOT system was implemented to allow authors to create subjective ontologies to be deployed for generating content within a range of culturally based narrative models – including African diasporic models of call and response interaction. Development of these aspects of the GRIOT system involved critical engagement with several of the issues considered in this construal of African diasporic orature, at multiple levels. {#para57}

Certainly, as in any process of cultural production, a particular world-view informed the development of the GRIOT system, including its reliance upon particular cognitive scientific theories, and its initial areas of application. I would stress, however, that its development was by-and-large a technical practice (my computer science Ph.D. dissertation project), firmly employing software engineering techniques, and influenced by the value systems of the engineering discipline. Yet, the narrative models, applications, claims, and goals may have been based in cultural traditions and values typically absent from computer science discussions. One of these cultural traditions resonates strongly with Ngugi’s formulation of orature (and my reframing of Ngugi’s model as African diasporic orature) (Ngugi, 1998). {#para58}

I propose that GRIOT involves African diasporic orature in at least the following ways: {#para59}

- The basis in cognitive semantics allows for a systematic approach to culture that admits concerns such as orature into my computational practice.

- The architecture allows computational narrative authors to enable subjective content generation and improvisational, collaborative relationships with the audience/users.

- Interaction with polymorphic poetry is structured as call and response interaction as opposed to command execution.

- Polymorphic poetry implemented in GRIOT addresses issues related to African diasporic orature and relies upon thematic ontologies in which questions explicitly related to the African diasporic contexts are raised.

- Oral performance has been central to polymorphic poetry execution and performative deployment has been theorized as one of four levels of using GRIOT.

A discussion of each of these involvements of African diasporic orature follows. {#para60}

**Cognitive Semantics and Orature in GRIOT** {#para61}

GRIOT’s knowledge representation structures are rooted in the cognitive semantics theory of conceptual blending (the human ability to dynamically, systematically, and optimally integrate concepts). The cognitive semantics framework paves the way for systematic approach to cultural concerns. Empirical research in cognitive semantics suggests that language activity is only the observable result of processes in which humans draw upon ‘a vast array of cognitive resources’ involving ‘innumerable models and frames, set up multiple connections, coordinate large arrays of information, engage in creative mappings, transfers, and elaborations’ (Fauconnier, 2000). Gilles Fauconnier has referred to these process of meaning construction as ‘Backstage Cognition’. The assertion that many aspects of backstage cognition are based upon shared cognitive structures or operate on the basis of general principles is referred to as ‘operational uniformity’ (Fauconnier, 2000). Cognitive semantics researchers see linguistic distributions (language phenomena across various levels of specificity) as only examples of observable manifestations of processes of backstage cognition with striking operational uniformity. This operational uniformity of processes underlying conceptual thought applies to our understanding and creation of cultural products regardless of the culture in which they are developed. This contrasts strongly with academic traditions such as cultural anthropology which seeks in part to understand cultural productions in its contextual particularity as opposed to uniform underlying cognitive processes. On this basis, the cognitive semantics foundation of my work applies just as readily to products of African diasporic orature as to any other form of cultural production or aesthetic systems. {#para62}

In Cognitive Dimensions of Social Science, Mark Turner (2001) raises Clifford Geertz’s description of the role of the anthropologist to make this point. He presents Geertz describing his brand of analyses as ‘not an experimental science in search of law but an interpretive one in search of meaning. It is explication I am after, construing social expressions on their surface enigmatical’ (Geertz, 1973; Turner, 2001). The nature of Geertz’s enterprise, what Turner (2001) calls the ‘historical retrospection’ and ‘particularity’ of the approach, contrasts strongly with the cognitive semantics focus on cognitive operations such as analogical inference, metaphorical mapping, and conceptual blending. The cognitive semantics approach is not a case of scientific reductionism however. On the contrary, the focus on operational uniformity provides cultural bridges between phenomena in diverse cultures. It provides a type of comparative interpretive analysis at the same time as providing an experimental analysis based upon ‘weighing data, making hypotheses, building models, offering explanations, sometimes offering even predictions or tactics for intervention’ (Turner, 2001). For example, George Lakoff and Mark Turner (1989) have analysed poetry by critically examining deployment of empirically determined culturally entrenched metaphors within particular poems. The cognitive semantics approach has allowed me access to elements of cultural narratives such as African diasporic orature that does not seek to exoticise them, but rather to understand their implications when mapped to the domain of computation. {#para63}

**Architectural Structure and Orature in GRIOT** {#para64}

The GRIOT architecture allows computational narrative authors to implement works involving subjective content generation and an improvisational, collaborative relationship to the audience. Cultural knowledge must be explicitly authored in the form of theme domains and phrase templates. The author defined event structure engine allows polypoem authors to also structure the sequence of user-input opportunities. The combination of these features echoes Ngugi’s (1998) observation within orature of ‘how the audience can play varying roles within performances, for example as critics, or as co-performers’. The relationship between user input and system output in GRIOT can be equally nuanced. This is exemplified by the varying relationship between input and output in examples of polymorphic poetry: e.g. in Walking Blues Changes Undersea user input affects the emotional disposition of the output, in The Girl with Skin of Haints and Seraphs user input selects how thematic identity constructs arising from stereotypical binary oppositions can be recombined, in The Griot Sings Haibun user input focuses the output on a particular aspect of Buddhist view of qualitative experience of everyday events (Harrell, 2005a; 2005b; 2006; 2007). This concern with improvisational meaning generation as enabled by collaboration with an audience is intentionally informed by an African diasporic oratory impulse. {#para65}

I tentatively suggest another more abstract influence of orature upon the GRIOT research goals. The general architecture of GRIOT is theorized to extend to non-textual media, such as the combination of images and dynamic computer graphics, as well. While this can be interpreted as an example of the engineering value of generalisability, it can also be seen as exemplifying the African diasporic oratory value of integrative arts. Though this discussion of orature’s influence upon the GRIOT architecture can be seen as a rational reconstruction of the systems underlying values, I believe that the influence is more profound. The expressive aims of the initial polypoems created in GRIOT were explicitly created with improvisational narrative forms based in African diasporic orature in mind. {#para66}

**Call and Response Interaction and Orature in GRIOT** {#para67}

The Girl with Skin of Haints and Seraphs polypoem provides a commentary on racial politics, the limitations of simplistic binary views of social identity, and the need for more contingent, dynamic models of social identity. The dynamic nature of social identity is also reflected in the way the program produces different poems with different novel metaphors each time it is run. It draws on a set of ontologies providing structured knowledge about domains such as skin, angels, demons,Europe, an Africa, given as sets of axioms. Interaction with The Girl with Skin of Haints and Seraphs invokes attributes of African diasporic orature. As described previously in Harrell (2007), dynamic improvisation and call and response structures are familiar aspects of Pan-African narrative forms as diverse as the African Brazilian martial art and dance Capoeira Angola, Charles Mingus’ calling out of the segregationist Governor of Arkansas in ‘Fables of Faubus’ from Mingus (1960), the penetratingly satirical fiction of Ishmael Reed, and hip-hop freestyle rhyming. The output of The Girl with Skin of Haints and Seraphs is founded in African and African American vernacular traditions of signification (Gates Jr, 1988). An example of output from The Girl with Skin of Haints and Seraphs follows (Harrell, 2005a): {#para68}

**>africa**

every night she wakes covered with winged-creature original-lady sweat {#para69}

**>africa**

she nearly died while choking on lady black candy

skin black ideas and miserable thoughts whipped through her {#para70}

**>europe**

her failure was ignoring her scaled-being sunbather nature

and her pride privilege feet danced {#para71}

**>europe**

she worked raising ashy-skin wintery-skin children of her own

and her mathematics bullet feet danced {#para72}

**> angel**

she finally knew that a privilege love woman would never be loved {#para73}

The output reveals the intention behind the knowledge base provided by the author. Stereotypes of both Africanness (the ‘original lady’ with ‘skin black’) and Europeanness (the ‘sunbather’ with ‘wintery skin’) are conjugated differently upon each execution. {#para74}

For contrast, another execution with the same user input reads: {#para75}

**>africa**

her arrival onto this earth was marked – black ghost knows longing and fear {#para76}

**>africa**

her wax hot drips anansi bitemarks in the flesh and psyche of hope loss loves

her condition was melaninated impoverished-elder-like {#para77}

**>europe**

tears ran relay races between her combination-skin bullet eyes and her pain entitlement earlobes and back|

longing awe ideas and miserable thoughts whipped through her {#para78}

**>europe**

when hungry she dined on shame smugness rice and female imperialist yams

life was an astounding miracle {#para79}

**> angel**

her pointed-nose piercing-arrow spirit would live on {#para80}

A parallel structure can be found in many examples of call and response orature, for example in the words of the Capoeira Angola song ‘Ê Paraná’ (Harrell, 2005a): {#para81}

*Ê Paraná*

Eu não vou na sua casa, Paraná

*Ê Paraná*

Pra você não ir na minha, Paraná

*Ê Paraná*

Porque você tem boca grande, Paraná

*Ê Paraná*

Vai comer minha galinha, Paraná

*Ê Paraná*

Puxa, puxa, leva, leva, Paraná

*Ê Paraná*

Paraná está me chamando, Paraná

… {#para82}

The song excerpt translates in English roughly as (Harrell, 2005a): {#para83}

*Eh, Paraná*

I do not go in your house, Paraná

*Eh, Paraná*

For you go not in mine, Paraná

*Eh, Paraná*

Because you have a great mouth, Paraná

*Eh, Paraná*

You will eat my chicken, Paraná

*Eh, Paraná*

Pull, pull, take, take, Paraná

*Eh, Paraná*

Paraná is calling me, Paraná

… {#para84}

The repeated invocation of an historic place in the ‘New World’ is a common theme in African diasporic call-and-response lyrics. When these songs are sung, new lyrics are often spontaneously improvised. The creation of traditionally structured songs with new meanings, especially layered meanings as in capoeira songs (the songs often have double and triple functions within the art form) also serves to create new identities for postcolonial contexts. The output from The Girl with Skin of Haints and Seraphs above was enabled by the polypoems intended affordance for supporting precisely this type of emergent content via participation in its call and response structure. {#para85}

**Social Commentary and Orature in GRIOT** {#para86}

In the previous subsection we have seen GRIOT used to implement polypoems in the service of social commentary, for example to critique narrow reliance upon power relationships of binary opposition in identity politics (e.g. in stereotypical oppositions such as male vs. female, black vs. white, oriental vs. occidental) (Harrell, 2005a). Similarly, GRIOT was used by Joseph Goguen, in collaboration with the author, to implement a polymorphic version of Goguen’s poem November Qualia (used as content in the performance The Griot Sings Haibun), which describes singular moments of qualitative experience from a Buddhist perspective (Goguen, 2005a; 2005b). Sample output from this polypoem follows: {#para87}

qualia are moments of luminous world,

empty, suffering, compassion

mind body snapshots

neither arising, departing, or dwelling

gone beyond

gone far beyond {#para88}

6:41 am

mind cloud ocean

unmoved moving trees

connecting blue high, blue emptiness flesh

forever being sky

timeless, perfected tender self {#para89}

6:53 am

the pipes:-

connecting, pipes of compassion

vivid bolted

shining, empty

neither atomic nor not

always connecting

timeless, perfected

beyond being beyond {#para90}

7:26 pm

save us from fear, wanting

addict & moonlight, wanting & timeless forgotten

bright grasping fear

vultures of mind, forever circling

embracing transient form

ecstatic revulsion, wanting {#para91}

1:47 am

translucent flesh, tender, inscrutable

unending mother ocean

biomass being, vital & vivid

all connected, empty, void

burning mind & self

ecstatic tender burning void {#para92}

In both The Girl with Skin of Haints and Seraphs and the polymorphic version of November Qualia, particular world-views provide the impetus for the expressive statement being made. Both polypoems suggest transcendental philosophies, yet the production of each polypoem was grounded in the medium in which it was created. This primacy of culturally grounded subject matter reflects the integrative character of African diasporic orature. The applications of GRIOT are grounded in particular cultural forms (such as prose poetry or haibun poetry), informed by cultural world-views (such as marginalized African diasporic or Tibetan Buddhist perspectives), and the role of these cultural influences is foregrounded in the authors’ statements about these poems. The simple act of foregrounding such concerns is uncommon within computing practices, but I feel it is not problematic because underlying cultural values are explicitly and critically addressed in their relationship to the computational system. {#para93}

**Performance and GRIOT** {#para94}

The polypoems implemented with GRIOT have most often been presented via performance. In Second Person, Pat Harrigan and Noah Wardrip-Fruin (2007) refer to such work as ‘performances [that] take place in both the real and digital worlds’. The most notable case of this was The Griot Sings Haibun polypoem, which was used in a live performance with free jazz musicians (Goguen and Harrell, 2005; Harrell, 2007). During the performance, the graphical user interface (GUI) was projected onto a large screen behind the performers for the audience to see. The GUI was mirrored on a plasma screen facing the performers so that the musicians and orator (Goguen) could see. The author acted as a polypoem system performer, improvisationally generating text output from the November Qualia polypoem and selecting corresponding multimedia imagery based on what the musicians played. The musicians could also respond improvisationally to the text visible on the plasma screen. In this sense the performance was a collective improvisation. Using the GUI for The Griot Sings Haibun, the system performer selected the desired clause type using buttons arranged in a row at the top of the screen. The user selected a clause by clicking on one of the keywords (e.g. ‘self’, ‘empty’, or ‘other’) on the bottom one-third of the screen. This selected use of particular ontology related to the authors’ Buddhist themes of self, other, emptiness, and related concepts. At various times, clauses of only particular types would appear on the screen and would be regenerated on-the-fly. Thus, during performance the discourse structure was much more dynamic and variable than in the pure LISP interface. Several examples of haibun poetry were implemented, and buttons along the bottom of the screen allowed the performer to shift from one haibun polypoem to another. This also shifted between background images composed by the author (some of the backgrounds were created using photographs taken by Joseph Goguen as raw images). {#para95}

Such a performance consolidates many of the characteristics of orature presented by Ngugi (1998). The performance took place in a particular architectural environment (on stage), with performers arranged in a circle (including the plasma screen feedback to the musicians as a ‘performer’. The lighting was controlled and focused audience attention on different performers at different times. The performance featured real-time generation of output from the polypoem. The timing of particular utterances and musical phrases was orchestrated by the collective improvisation of the group. The polypoem was used improvisationally as well, generating lines at a pace determined by feedback from the orator, musicians, and perceived audience response. Finally, the projected backdrop served as a type of performative mises-en-scène. All of these aspects of the performance reflect a concern for the performance conditions of architectural space, time-frame, performer-audience relationship, and mises-en-scène {#para96}

### Conclusion, Troublesome Spectres, and Future Directions

If any point is to be made by the discussion above, it is that new expressive and technical possibilities of computing can be rooted in diverse cultural values and practices. This is not new to computing, indeed computational artifacts are ubiquitous within the worlds many cultural contexts. However, computer science research typically renders cultural values only implicitly, and when they are made explicit they typically reflect a privileged value system within Western culture such as the rationalist tradition so well articulated by Winograd and Flores (1986). African diasporic orature provide one interpretive frame for considering the GRIOT system, the cultural value that may be implicit within its architecture, its intended areas of application, and the performative deployment of computational narratives created with it. {#para97}

In constructing my argument, I have tried to anticipate a wide range of criticism, especially criticism based in a set of heinous and haunting social constructs. I am haunted by ghosts of an essentialising ‘African primitiveness’ exemplified by the ‘savage mind’ critiqued by Mudimbe in the Eglash quotation above, or the linguistic determinism in the binary view of culture put forth by Ong and others. I am haunted by critiques of essentialist cultural buttressing (against oppressive and disempowering alternatives) exhibited by a subset of African diasporic cultural or performance theory such as that of Kwesi Owusu (described above in subsection 4.1). Furthermore, I have risked the same criticism by invoking Ngugi and his nuanced argument that differentiates between explicitly shared value systems that inform cultural practices, and essentialist value systems that posit intrinsic characteristic of individuals or groups as the sole bases for cultural practices. I certainly risk the perception that I conflate my own identity with an idealized form of cultural production. Any of these concerns could potentially overshadow the core argument being made here. Nonetheless, I have attempted to capture a careful, if preliminary, argument of the value of making cultural concerns explicit in computing practice, and, in the case of African diasporic orature, very specific analytical and productive gains that can be made. {#para98}

One quite promising future direction is to explore, develop, and adopt methods for making the often implicit values within technology and its uses explicit. Toward this end, Callon and Latour’s Actor-Network Theory seems promising. It is an alternative sociology focused upon tracing associations between agents as opposed to reductive explanations based solely upon quantitative data. It emphasizes examining the roles on non-humans (e.g. computational technology) and the construction or reassembling of new social concepts and procedures (Latour, 2005). In Actor-Network Theory there is also an emphasis on tracing the ‘diversity of agencies’ at once operating in the world, assembling and reassembling social networks. It suggests following statements such as Owusu’s from subsection 4.1 above: ‘this state of consciousness, a reflection of African and Asian attitudes to creativity, is what is called orature’, and avoid to explain them away in convenient social terms such as ‘essentialism’. Instead, it is far more telling to trace the exchange of values between such actors, their artifacts, and associates via such statements. In the case of African diasporic orature, a cursory tracing of associations revealed a unique conception of the ‘oral’ in which medium is not the primary consideration that underlies a wide range of artistic creations. When computational media are considered in this light, a systematic and clarifying approach to making cultural foundations explicit is necessary and could help to further push the aims of this paper: diversifying the range of innovative computing practices. {#para99}

## Author’s Biography

Fox Harrell is a researcher, author, and artist exploring the relationship between imaginative cognition and computation. He and his laboratory, the Imagination, Computation, and Expression [ICE] Lab/Studio develop new forms of computational narrative, gaming, and related digital infrastructures and technical-cultural media with a basis in computer science, cognitive science, and digital media arts. He is an Assistant Professor of Digital Media in the department of Literature, Communication, and Culture at the Georgia Institute of Technology.

## References

Agre, P. E. Computation and Human Experience (Cambridge, U.K.: Cambridge University Press, 1997).

Biakolo, E. ‘On the Theoretical Foundations of Orality and Literacy’, Research in African Literatures 30 (Summer 1999): 42-65.

Bolter, J. D. and R. Grusin. Remediation: Understanding New Media (Cambridge, MA: MIT Press, 1999).

Descartes, R. Meditations on First Philosophy: With Selections from the Objections and Replies (Cambridge, U.K.: Cambridge University Press, 1996).

Dobbs, B. J. T. The Janus Faces of Genius: The Role of Alchemy in Newton’s Thought (Cambridge, U.K.: Cambridge University Press, 1991).

Dourish, P. Where the Action Is: The Foundation of Embodied Interaction (Cambridge,MA: MIT Press, 2001).

Dreyfus, H. L. What Computers Still Can’t Do: A Critique of Artificial Reason (Cambridge, MA: MIT Press, 1992).

Eglash, R. ‘African Influences in Cybernetics’, in C.H. Gray (ed.) The Cyborg Handbook (London, U.K.: Routledge, 1995).

Fauconnier, G. ‘Methods and Generalizations’, in T. Janssen and G. Redeker (eds) Scope and Foundations of Cognitive Linguistics (The Hague: Mouton De Gruyter, 2000): 95-127.

Fauconnier, G. and M. Turner. The Way We Think: Conceptual Blending and the Mind’s Hidden Complexities (New York: Basic Books, 2002).

Finnegan, R. Literacy and Orality: Studies in the Technology of Communication (Oxford, U.K.: Basil Blackwell, 1988).

Gates Jr., H. L. The Signifying Monkey: A Theory of African-American Literary Criticism (New York: Oxford, 1988).

Geertz, C. The Interpretation of Cultures (New York, NY: Basic Books, 1973).

Goguen, J. ‘An Introduction to Algebraic Semiotics, with Applications to User Interface Design’, in Computation for Metaphors, Analogy, and Agents (Yakamatsu, Japan, 1998).

Goguen, J. and D.F. Harrell. ‘Style as a Choice of Blending Principles’, in Style and Meaning in Language, Art, Music and Design, Proceedings of the 2004 AAAI Fall Symposium (Washington D.C., 2004).

Goguen, J. ‘November Qualia’, Journal of Consciousness Studies vol. 12 (2005a): 73.

Goguen, J. ‘GRIOT “November Qualia” Output’, vol. 2007(2005b).

Goguen, J. and D.F. Harrell. ‘The Griot Sings Haibun’,La Jolla (2005), UCSD CalIT2 Opening Performance.

Goguen, J. and D.F. Harrell. ‘Style as a Choice of Blending Principles’, inS. Argamon, K. Burns, andS. Dubnov (eds) The Structure of Style: Algorithmic Approaches to Understanding Manner and Meaning (Berlin: Springer, 2006).

Harrell, D. F. ‘Algebra of Identity: Skin of Wind, Skin of Streams, Skin of Shadows, Skin of Vapor’, CTheory (2005a).

Harrell, D. F. ‘Shades of Computational Evocation and Meaning: The GRIOT System and Improvisational Poetry Generation’, in Proceedings of the 6th Digital Arts and Culture Conference, (2005b): 133-143.

Harrell, D. F. ‘Walking Blues Changes Undersea: Imaginative Narrative in Interactive Poetry Generation with the GRIOT System’, in AAAI 2006 Workshop in Computational Aesthetics: Artificial Intelligence Approaches to Happiness and Beauty,Boston, MA (2006).

Harrell, D. F. ‘GRIOT’s Tales of Haints and Seraphs: A Computational Narrative Generation System’, in N. Wardrip-Fruin and P. Harrigan (eds) Second Person: Role-Playing and Story in Games and Playable Media (Cambridge,MA: MIT Press, 2007).

Harrigan, P. and N. Wardrip-Fruin. Second Person: Role-Playing and Story in Games and Playable Media (,MA: MIT Press, 2007).

Lakoff, G. and M. Turner. More than cool reason — a field guide to poetic metaphor. (Chicago, IL: University of Chicago Press, 1989).

Latour, B. Reassembling the Social: An Introduction to Actor-Network-Theory (Oxford,U.K.:OxfordUniversity Press, 2005).

Manovich, L. The Language of New Media (Cambridge,: MIT Press, 2001).

McCullock, W. S. and W. Pitts. ‘A logical calculus of the ideas immanent in nervous activity’, Bulletin of Mathematical Biophysics, vol. 5 (1942): 115-143.

Mingus, C. ‘Charles Mingus Presents Charles Mingus’, Candid Records, 1960.

Ngugi, w. T. o. Penpoints, Gunpoints, and Dreams: Towards a Critical Theory of the Arts and the State in Africa (Oxford, U.K.: Oxford University Press, 1998).

Ong, W. Orality and Literacy: The Technologizing of the Word (London, U.K.: Methuen, 1982).

Owusu, K. Storms of the Heart (London, U.K.: Camden, 1988).

Reed,I. Yellow Back Radio Broke-Down (New York, NY: Doubleday, 1969).

Traditional song, ‘Ê Paraná’.

Turner, M. Cognitive Dimensions of Social Science: The Way We Think About Politics, Economics, Law, and Society (New York,>NY:OxfordUniversity Press, 2001).

von Neumann, J. ‘First Draft of a Report on the EDVAC’, Moore School of Electrical Engineering,University ofPennsylvania,Philadelphia (June 30, 1945).

Winograd, T. and F.Flores. Understanding Computers and Cognition: A New Foundation for Design (Norwood, NJ: Albex Corporation, 1986).
