# Bundled tool catalogue

Biomni-Lite registers **225 bundled tools** from the Biomni tool library (in `biomni/tool/`). The agent searches this catalogue with `find_tools` and calls the tools it needs. Some tools need optional software or data; the app reports which tools are ready on your computer, in **Resources → Tools** and in the agent's activity log.

The list below is generated from the registry. Descriptions are the tools' own.

## Modules

| Module | Tools |
|---|---|
| `database` | 40 |
| `pharmacology` | 25 |
| `genomics` | 19 |
| `molecular_biology` | 18 |
| `microbiology` | 12 |
| `physiology` | 11 |
| `bioimaging` | 10 |
| `immunology` | 10 |
| `genetics` | 9 |
| `literature` | 8 |
| `synthetic_biology` | 8 |
| `bioengineering` | 7 |
| `pathology` | 7 |
| `systems_biology` | 7 |
| `biochemistry` | 6 |
| `cancer_biology` | 6 |
| `cell_biology` | 5 |
| `protocols` | 4 |
| `support_tools` | 4 |
| `biophysics` | 3 |
| `glycoengineering` | 3 |
| `lab_automation` | 3 |

## biochemistry (6)

| Tool | Description |
|---|---|
| `analyze_circular_dichroism_spectra` | Analyzes circular dichroism (CD) spectroscopy data to determine secondary structure and thermal stability. |
| `analyze_enzyme_kinetics_assay` | Performs in vitro enzyme kinetics assay and analyzes the dose-dependent effects of modulators. |
| `analyze_itc_binding_thermodynamics` | Analyzes isothermal titration calorimetry (ITC) data to determine binding affinity and thermodynamic parameters. |
| `analyze_protease_kinetics` | Analyze protease kinetics data from fluorogenic peptide cleavage assays, fit the data to Michaelis-Menten kinetics, and determine key kinetic parameters. |
| `analyze_protein_conservation` | Perform multiple sequence alignment and phylogenetic analysis to identify conserved protein regions. |
| `analyze_rna_secondary_structure_features` | Calculate numeric values for various structural features of an RNA secondary structure. |

## bioengineering (7)

| Tool | Description |
|---|---|
| `analyze_calcium_imaging_data` | Analyze calcium imaging data to quantify neuronal activity metrics including cell counts, event rates, decay times, and signal-to-noise ratios. |
| `analyze_cell_migration_metrics` | Analyze cell migration metrics from time-lapse microscopy images. |
| `analyze_in_vitro_drug_release_kinetics` | Analyzes in vitro drug release kinetics from biomaterial formulations. |
| `analyze_myofiber_morphology` | Quantifies morphological properties of myofibers in microscopy images of tissue sections. |
| `decode_behavior_from_neural_trajectories` | Model neural activity trajectories and decode behavioral variables. |
| `perform_crispr_cas9_genome_editing` | Simulates CRISPR-Cas9 genome editing process including guide RNA design, delivery, and analysis. |
| `simulate_whole_cell_ode_model` | Simulate a whole-cell model represented as a system of ordinary differential equations (ODEs). |

## bioimaging (10)

| Tool | Description |
|---|---|
| `batch_register_images` | Perform batch registration of multiple images to a single reference image. Automatically processes all medical image files in a directory and registers them to the fixed reference. Supports rigid, affine, or deformable registration for all images. |
| `calculate_similarity_metrics` | Calculate similarity metrics between two medical images. Supports mutual information, mean squared error, correlation, and normalized cross correlation. |
| `create_registration_visualization` | Create visualization plots for registration results. Generates comparison plots, difference images, overlays, and metric charts. |
| `create_segmentation_visualization` | Create and save visualization of segmentation results using nilearn. Generates overlay plots and multiple anatomical views. |
| `prepare_input_for_nnunet` | Prepare input data for nnUNet by handling both 4D and pre-split modality files. Automatically detects file format and prepares data accordingly. |
| `quick_affine_registration` | Perform affine image registration between two medical images using SimpleITK. Affine registration handles translation, rotation, scaling, and shearing. More flexible than rigid registration but still preserves parallel lines. |
| `quick_deformable_registration` | Perform deformable (B-spline) image registration between two medical images using SimpleITK. Deformable registration allows for local non-linear transformations, handling complex deformations. Most flexible but computationally intensive registration method. |
| `quick_rigid_registration` | Perform rigid image registration between two medical images using SimpleITK. Rigid registration handles translation and rotation only, preserving shape and size. Includes preprocessing, similarity metrics calculation, and visualization generation. |
| `segment_with_nn_unet` | Segment images using nnUNet with proper environment setup. Supports brain tumor segmentation and other medical image segmentation tasks. |
| `split_modalities` | Split a 4D NIfTI file into separate modality files for nnUNet processing. Handles BRATS dataset format with FLAIR, T1w, t1gd, and T2w modalities. |

## biophysics (3)

| Tool | Description |
|---|---|
| `analyze_cell_morphology_and_cytoskeleton` | Quantifies cell morphology and cytoskeletal organization from fluorescence microscopy images. |
| `analyze_tissue_deformation_flow` | Quantify tissue deformation and flow dynamics from microscopy image sequence. |
| `predict_protein_disorder_regions` | Predicts intrinsically disordered regions (IDRs) in a protein sequence using IUPred2A. |

## cancer_biology (6)

| Tool | Description |
|---|---|
| `analyze_cell_senescence_and_apoptosis` | Analyze flow cytometry data to quantify senescent and apoptotic cell populations. |
| `analyze_copy_number_purity_ploidy_and_focal_events` | CNVkit-based copy number workflow performing CNV segmentation, purity & ploidy approximation, simplified HRD-style metrics, and focal amplification/deletion detection in selected genes. |
| `analyze_ddr_network_in_cancer` | Analyze DNA Damage Response (DDR) network alterations and dependencies in cancer samples. |
| `detect_and_annotate_somatic_mutations` | Detects and annotates somatic mutations in tumor samples compared to matched normal samples using GATK Mutect2 for variant calling, GATK FilterMutectCalls for filtering, and SnpEff for functional annotation. |
| `detect_and_characterize_structural_variations` | Detects and characterizes structural variations (SVs) in genomic sequencing data using LUMPY for SV detection followed by annotation with COSMIC and/or ClinVar databases. |
| `perform_gene_expression_nmf_analysis` | Performs Non-negative Matrix Factorization (NMF) on gene expression data to extract metagenes and their associated sample weights for tumor subtype identification. |

## cell_biology (5)

| Tool | Description |
|---|---|
| `analyze_flow_cytometry_immunophenotyping` | Analyze flow cytometry data to identify and quantify specific cell populations based on surface markers. |
| `analyze_mitochondrial_morphology_and_potential` | Quantifies metrics of mitochondrial morphology and membrane potential from fluorescence microscopy images. |
| `perform_facs_cell_sorting` | Performs Fluorescence-Activated Cell Sorting (FACS) to enrich cell populations based on fluorescence characteristics. |
| `quantify_and_cluster_cell_motility` | Quantify cell motility features from time-lapse microscopy images and cluster cells based on motility patterns. |
| `quantify_cell_cycle_phases_from_microscopy` | Quantify the percentage of cells in each cell cycle phase using Calcofluor white stained microscopy images. |

## database (40)

| Tool | Description |
|---|---|
| `blast_sequence` | Identify a DNA or protein sequence using NCBI BLAST. |
| `get_genes_near_ccre` | Given a cCRE accession, return k nearest genes sorted by distance. |
| `query_alphafold` | Query the AlphaFold Database API for protein structure predictions or metadata; optionally download structures. |
| `query_cbioportal` | Query the cBioPortal REST API using natural language or a direct endpoint. |
| `query_chembl` | Query the ChEMBL REST API via natural language, direct endpoint, or identifiers (chembl_id, smiles, molecule_name). |
| `query_clinicaltrials` | Query the ClinicalTrials.gov API v2 using natural language or a direct endpoint. |
| `query_clinvar` | Convert a natural language prompt into a structured ClinVar search query and run it. |
| `query_dailymed` | Query the DailyMed RESTful API using natural language or a direct endpoint. |
| `query_dbsnp` | Query the NCBI dbSNP database using natural language or direct search term. |
| `query_emdb` | Query the Electron Microscopy Data Bank (EMDB) using natural language or a direct endpoint. |
| `query_encode` | Query the ENCODE Portal API to locate functional genomics data (experiments, files, biosamples, datasets). |
| `query_ensembl` | Query the Ensembl REST API using natural language or a direct endpoint. |
| `query_geo` | Query the NCBI GEO database (GDS/GEOPROFILES) using natural language or direct search term. |
| `query_gnomad` | Query gnomAD for variants in a gene using natural language or direct gene symbol. |
| `query_gtopdb` | Query the Guide to PHARMACOLOGY (GtoPdb) database using natural language or a direct endpoint. |
| `query_gwas_catalog` | Query the GWAS Catalog API using natural language or a direct endpoint. |
| `query_interpro` | Query the InterPro REST API using natural language or a direct endpoint. |
| `query_iucn` | Query the IUCN Red List API using natural language or a direct endpoint. |
| `query_jaspar` | Query the JASPAR REST API for transcription factor binding profiles. |
| `query_kegg` | Take a natural language prompt and convert it to a structured KEGG API query. |
| `query_monarch` | Query the Monarch Initiative API using natural language or a direct endpoint. |
| `query_mpd` | Query the Mouse Phenome Database (MPD) using natural language or a direct endpoint. |
| `query_openfda` | Query the OpenFDA API using natural language or direct parameters. |
| `query_opentarget` | Query the OpenTargets Platform API using natural language or a direct GraphQL query. |
| `query_paleobiology` | Query the Paleobiology Database (PBDB) API using natural language or a direct endpoint. |
| `query_pdb` | Query the RCSB PDB database using natural language or a direct structured query. |
| `query_pdb_identifiers` | Retrieve detailed data and/or download files for PDB identifiers. |
| `query_pride` | Query the PRIDE proteomics database using natural language or a direct endpoint. |
| `query_pubchem` | Query the PubChem PUG-REST API using natural language or a direct endpoint. |
| `query_quickgo` | Query the QuickGO API using natural language or a direct endpoint. |
| `query_reactome` | Query the Reactome database using natural language or a direct endpoint; optionally download pathway diagrams. |
| `query_regulomedb` | Query the RegulomeDB database using natural language or direct endpoint. |
| `query_remap` | Query the ReMap database for regulatory elements and transcription factor binding. |
| `query_stringdb` | Query the STRING protein interaction database using natural language or direct endpoint. |
| `query_synapse` | Query Synapse REST API for biomedical datasets/files using natural language or structured search parameters. Supports optional authentication via SYNAPSE_AUTH_TOKEN. |
| `query_ucsc` | Query the UCSC Genome Browser API using natural language or a direct endpoint. |
| `query_unichem` | Query the UniChem 2.0 REST API using natural language or a direct endpoint. |
| `query_uniprot` | Query the UniProt REST API using either natural language or a direct endpoint. |
| `query_worms` | Query the World Register of Marine Species (WoRMS) REST API using natural language or a direct endpoint. |
| `region_to_ccre_screen` | Given genomic coordinates, retrieve intersecting ENCODE SCREEN cCREs. |

## genetics (9)

| Tool | Description |
|---|---|
| `analyze_cas9_mutation_outcomes` | Analyzes and categorizes mutations induced by Cas9 at target sites. |
| `analyze_crispr_genome_editing` | Analyzes CRISPR-Cas9 genome editing results by comparing original and edited sequences. |
| `analyze_protein_phylogeny` | Perform phylogenetic analysis on a set of protein sequences. This function aligns sequences, constructs a phylogenetic tree, and visualizes evolutionary relationships. |
| `bayesian_finemapping_with_deep_vi` | Performs Bayesian fine-mapping from GWAS summary statistics using deep variational inference to compute posterior inclusion probabilities and credible sets for putative causal variants. |
| `fit_genomic_prediction_model` | Fit a linear mixed model for genomic prediction using genotype and phenotype data. |
| `identify_transcription_factor_binding_sites` | Identifies binding sites for a specific transcription factor in a genomic sequence. |
| `liftover_coordinates` | Perform liftover of genomic coordinates between hg19 and hg38 formats with detailed intermediate steps. |
| `perform_pcr_and_gel_electrophoresis` | Performs PCR amplification of a target transgene and visualizes results using agarose gel electrophoresis. |
| `simulate_demographic_history` | Simulate DNA sequences with specified demographic and coalescent histories using msprime. |

## genomics (19)

| Tool | Description |
|---|---|
| `analyze_chromatin_interactions` | Analyze chromatin interactions from Hi-C data to identify enhancer-promoter interactions and TADs. |
| `analyze_comparative_genomics_and_haplotypes` | Perform comparative genomics and haplotype analysis on multiple genome samples. Aligns genome samples to a reference, identifies variants, analyzes shared and unique genomic regions, and determines haplotype structure. |
| `analyze_genomic_region_overlap` | Analyze overlaps between two or more sets of genomic regions. |
| `annotate_celltype_scRNA` | Annotate cell types based on gene markers and transferred labels using LLM. After leiden clustering, annotate clusters using differentially expressed genes and optionally incorporate transferred labels from reference datasets. |
| `annotate_celltype_with_panhumanpy` | Perform cell type annotation of single-cell RNA-seq data using Panhuman Azimuth Neural Network. This function implements the Panhuman Azimuth workflow for cell type annotation using the panhumanpy package, providing hierarchical cell type labels for tissues across the human body.  |
| `create_harmony_embeddings_scRNA` | Performs batch integration on single-cell RNA-seq data using Harmony and saves the integrated embeddings. |
| `create_scvi_embeddings_scRNA` | Create scVI and scANVI embeddings for single-cell RNA-seq data, saving the results to an AnnData object. |
| `find_enriched_motifs_with_homer` | Find DNA sequence motifs enriched in genomic regions using the HOMER motif discovery software. |
| `gene_set_enrichment_analysis` | Perform enrichment analysis for a list of genes, with optional background gene set and plotting functionality. |
| `generate_embeddings_with_state` | Generate State embeddings for single-cell RNA-seq data using the SE-600M model. This function downloads the SE-600M model from Hugging Face, installs required dependencies (git-lfs, uv, arc-state), and generates embeddings for the input AnnData object. The SE-600M model is a state-of-the-art embedding model for single-cell data that can capture complex biological patterns and cell states. Features include real-time streaming output, automatic retry with reduced batch size on failure, GPU detection and warnings, and input validation. |
| `generate_gene_embeddings_with_ESM_models` | Generate average protein embeddings for a list of Ensembl gene IDs using ESM (Evolutionary Scale Modeling) protein language models. This function fetches all protein isoform sequences for each gene, computes embeddings for each isoform using the specified ESM model and layer, then averages the embeddings across all isoforms to create a single representative embedding per gene. The embeddings are saved as PyTorch tensors for future use. Memory-friendly implementation with rolling averages, small batch processing, and automatic memory management. Automatically handles GPU/CPU device selection and includes error recovery for out-of-memory situations by falling back to single-sequence processing. |
| `generate_transcriptformer_embeddings` | Generate Transcriptformer embeddings for single-cell RNA-seq data. This function downloads model checkpoints, prepares the AnnData object with required fields (ensembl_id, raw counts, assay metadata), and runs inference to generate cell or gene embeddings. Transcriptformer is a transformer-based model that can learn rich representations of single-cell gene expression data. The function automatically handles Ensembl ID pattern detection, model downloading, data preprocessing, and creates missing assay metadata columns with 'unknown' values if needed. |
| `get_gene_set_enrichment_analysis_supported_database_list` | Returns a list of supported databases for gene set enrichment analysis. |
| `get_rna_seq_archs4` | Given a gene name, fetch RNA-seq expression data showing the top K tissues with highest transcripts-per-million (TPM) values. |
| `get_uce_embeddings_scRNA` | Generate UCE embeddings for single-cell RNA-seq data and map them to a reference dataset for cell type annotation. |
| `interspecies_gene_conversion` | Convert ENSEMBL gene IDs between different species using BioMart homology mapping. This function converts a list of ENSEMBL gene IDs from one species to their homologous counterparts in another species using the Ensembl BioMart database. The conversion is based on one-to-one ortholog mappings between species. |
| `map_to_ima_interpret_scRNA` | Map cell embeddings from the input dataset to the Integrated Megascale Atlas reference dataset using UCE embeddings. |
| `perform_chipseq_peak_calling_with_macs2` | Perform ChIP-seq peak calling using MACS2 to identify genomic regions with significant binding. |
| `unsupervised_celltype_transfer_between_scRNA_datasets` | Transfer cell type labels from an annotated reference scRNA-seq dataset to an unannotated query dataset using popV. Loads both AnnData .h5ad files, prepares count layers for scVI, processes the query against the reference, and runs selected annotation methods (default: SCANVI_POPV). Saves predictions to 'output_folder/popv_output/predictions.csv'. This function allows you to use different annotaiton methods i.e. CELLTYPIST, KNN_BBKNN, KNN_HARMONY, KNN_SCANORAMA, KNN_SCVI, ONCLASS, Random_Forest, SCANVI_POPV, Support_Vector, XGboost. Based on you transfer task you can select the multiple best annotation methods. Beware each annotation method adds computational requirements for running the tool. By default it uses SCANVI_POPV method. |

## glycoengineering (3)

| Tool | Description |
|---|---|
| `find_n_glycosylation_motifs` | Scan a protein sequence for canonical N-glycosylation sequons (N-X-[S/T], X≠P). Returns positions and motifs. |
| `list_glycoengineering_resources` | Curated list of external glycoengineering tools and resources (links and notes) as referenced in issue #198. |
| `predict_o_glycosylation_hotspots` | Heuristic O-glycosite hotspot prediction using local S/T density (lightweight baseline; see NetOGlyc 4.0 for SOTA). |

## immunology (10)

| Tool | Description |
|---|---|
| `analyze_atac_seq_differential_accessibility` | Perform ATAC-seq peak calling and differential accessibility analysis using MACS2. |
| `analyze_bacterial_growth_curve` | Analyzes bacterial growth curve data to determine growth parameters such as doubling time, growth rate, and lag phase. |
| `analyze_cfse_cell_proliferation` | Analyze CFSE-labeled cell samples to quantify cell division and proliferation. |
| `analyze_cns_lesion_histology` | Analyzes histological images of CNS lesions to quantify immune cell infiltration, demyelination, and tissue damage. |
| `analyze_cytokine_production_in_cd4_tcells` | Analyze cytokine production (IFN-γ, IL-17) in CD4+ T cells after antigen stimulation. |
| `analyze_ebv_antibody_titers` | Analyze ELISA data to quantify EBV antibody titers in plasma/serum samples. |
| `analyze_immunohistochemistry_image` | Analyzes immunohistochemistry images to quantify protein expression and spatial distribution. |
| `estimate_cell_cycle_phase_durations` | Estimate cell cycle phase durations using dual-nucleoside pulse labeling data and mathematical modeling. |
| `isolate_purify_immune_cells` | Simulates the isolation and purification of immune cells from tissue samples. |
| `track_immune_cells_under_flow` | Track immune cells under flow conditions and classify their behaviors. |

## lab_automation (3)

| Tool | Description |
|---|---|
| `get_pylabrobot_documentation_liquid` | Get the documentation for the liquid handling section of the PyLabRobot tutorial. |
| `get_pylabrobot_documentation_material` | Get the documentation for the material handling section of the PyLabRobot tutorial. |
| `test_pylabrobot_script` | Test a PyLabRobot script based on the script content. |

## literature (8)

| Tool | Description |
|---|---|
| `advanced_web_search_claude` | Initiate an advanced web search by launching a specialized agent to collect relevant information and citations through multiple rounds of web searches for a given query. |
| `extract_pdf_content` | Extract text content from a PDF file. |
| `extract_url_content` | Extract the text content of a webpage using requests and BeautifulSoup. |
| `fetch_supplementary_info_from_doi` | Fetches supplementary information for a paper given its DOI and saves it to a specified directory. |
| `query_arxiv` | Query arXiv for papers based on the provided search query. |
| `query_pubmed` | Query PubMed for papers based on the provided search query. |
| `query_scholar` | Query Google Scholar for papers based on the provided search query and return the first search result. |
| `search_google` | Search using Google search and return formatted results. |

## microbiology (12)

| Tool | Description |
|---|---|
| `analyze_arsenic_speciation_hplc_icpms` | Analyzes arsenic speciation in liquid samples using HPLC-ICP-MS technique. Returns a research log summarizing analysis steps and results. |
| `annotate_bacterial_genome` | Annotate a bacterial genome using Prokka to identify genes, proteins, and functional features. |
| `count_bacterial_colonies` | Count bacterial colonies from an image of agar plate using computer vision techniques. |
| `enumerate_bacterial_cfu_by_serial_dilution` | Quantify bacterial concentration (CFU/mL) using serial dilutions and spot plating. |
| `model_bacterial_growth_dynamics` | Model bacterial population dynamics over time using ordinary differential equations. |
| `optimize_anaerobic_digestion_process` | Optimize anaerobic digestion process conditions to maximize VFA production or methane yield. |
| `predict_rna_secondary_structure` | Predict the secondary structure of an RNA molecule using ViennaRNA. |
| `quantify_biofilm_biomass_crystal_violet` | Quantifies biofilm biomass using crystal violet staining assay data and returns a detailed research log. |
| `segment_and_analyze_microbial_cells` | Perform automated cell segmentation and quantify morphological metrics from fluorescence microscopy images. |
| `segment_cells_with_deep_learning` | Perform cell segmentation on fluorescence microscopy images using deep learning with pre-trained models from the Cellpose/Omnipose library. |
| `simulate_generalized_lotka_volterra_dynamics` | Simulate microbial community dynamics using the Generalized Lotka-Volterra (gLV) model. |
| `simulate_microbial_population_dynamics` | Performs stochastic simulation of microbial population dynamics using the Gillespie algorithm. |

## molecular_biology (18)

| Tool | Description |
|---|---|
| `align_sequences` | Align short sequences (primers) to a longer sequence, allowing for one mismatch. Checks both forward and reverse complement strands. |
| `annotate_open_reading_frames` | Find all Open Reading Frames (ORFs) in a DNA sequence using Biopython, searching both forward and reverse complement strands. |
| `annotate_plasmid` | Annotate a DNA sequence using pLannotate's command-line interface. |
| `design_golden_gate_oligos` | Design complementary oligonucleotides with Type IIS restriction enzyme overhangs for Golden Gate assembly based on restriction site analysis of the backbone. |
| `design_knockout_sgrna` | Design sgRNAs for CRISPR knockout by searching pre-computed sgRNA libraries. Returns optimized guide RNAs for targeting a specific gene. |
| `design_primer` | Design a single primer within the given sequence window. |
| `design_verification_primers` | Design Sanger sequencing primers to verify a specific region in a plasmid. First tries to use primers from an existing primer pool. If they cannot fully cover the region, designs additional primers as needed. |
| `digest_sequence` | Simulates restriction enzyme digestion of a DNA sequence and returns the resulting fragments with their properties. |
| `find_restriction_enzymes` | Finds common restriction enzyme sites in a DNA sequence and returns their cut positions. |
| `find_restriction_sites` | Identifies restriction enzyme sites in a given DNA sequence for specified enzymes. |
| `find_sequence_mutations` | Compare query sequence against reference sequence to identify mutations. |
| `get_bacterial_transformation_protocol` | Return a standard protocol for bacterial transformation. |
| `get_gene_coding_sequence` | Retrieves the coding sequence(s) of a specified gene from NCBI Entrez. |
| `get_golden_gate_assembly_protocol` | Return a customized protocol for Golden Gate assembly based on the number of inserts and specific DNA sequences. |
| `get_oligo_annealing_protocol` | Return a standard protocol for annealing oligonucleotides without phosphorylation. |
| `get_plasmid_sequence` | Unified function to retrieve plasmid sequences from either Addgene or NCBI. If is_addgene is True or identifier is numeric, uses Addgene. Otherwise searches NCBI using the plasmid name. |
| `golden_gate_assembly` | Simulate Golden Gate assembly to predict final construct sequences from backbone and fragment sequences. |
| `pcr_simple` | Simulate PCR amplification with given primers and sequence. |

## pathology (7)

| Tool | Description |
|---|---|
| `analyze_aortic_diameter_and_geometry` | Analyze aortic diameter and geometry from cardiovascular imaging data to measure aortic root diameter, ascending aorta diameter, and calculate geometric parameters such as tortuosity and dilation indices. |
| `analyze_atp_luminescence_assay` | Analyze luminescence-based ATP assay data to determine intracellular ATP concentration. |
| `analyze_bone_microct_morphometry` | Analyze bone microarchitecture parameters from 3D micro-CT images to calculate bone mineral density, bone volume, trabecular number, thickness, and separation. |
| `analyze_intracellular_calcium_with_rhod2` | Analyzes intracellular calcium concentration using Rhod-2 fluorescent indicator from microscopy images. |
| `analyze_thrombus_histology` | Analyze histological images of thrombus samples stained with H&E to identify and quantify different thrombus components (fresh, cellular lysis, endothelialization, fibroblastic reaction). |
| `quantify_corneal_nerve_fibers` | Quantify the volume/density of immunofluorescence-labeled corneal nerve fibers. |
| `segment_and_quantify_cells_in_multiplexed_images` | Segment cells and quantify protein expression levels from multichannel tissue images. |

## pharmacology (25)

| Tool | Description |
|---|---|
| `analyze_accelerated_stability_of_pharmaceutical_formulations` | Analyzes the stability of pharmaceutical formulations under accelerated storage conditions. |
| `analyze_fda_safety_signals` | Analyze safety signals across multiple drugs using OpenFDA adverse event data to identify patterns and comparative risk profiles. |
| `analyze_interaction_mechanisms` | Analyze interaction mechanisms between two specific drugs providing detailed mechanistic insights and clinical significance assessment. |
| `analyze_pixel_distribution` | Analyze western blot or DNA electrophoresis images and return pixel distribution statistics including intensity statistics, percentiles, and brightness distribution. Use this to determine appropriate threshold values for find_roi_from_image. |
| `analyze_radiolabeled_antibody_biodistribution` | Analyze biodistribution and pharmacokinetic profile of radiolabeled antibodies. |
| `analyze_western_blot` | Performs densitometric analysis of Western blot images to quantify relative protein expression. |
| `analyze_xenograft_tumor_growth_inhibition` | Analyze tumor growth inhibition in xenograft models across different treatment groups. |
| `calculate_physicochemical_properties` | Calculate key physicochemical properties of a drug candidate molecule. |
| `check_drug_combination_safety` | Analyze safety of a drug combination for potential interactions using DDInter database with comprehensive risk assessment and clinical recommendations. |
| `check_fda_drug_recalls` | Check for FDA drug recalls and enforcement actions from the OpenFDA database to identify safety concerns and regulatory actions. |
| `docking_autodock_vina` | Performs molecular docking using AutoDock Vina to predict binding affinities between small molecules and a receptor protein. |
| `estimate_alpha_particle_radiotherapy_dosimetry` | Estimate radiation absorbed doses to tumor and normal organs for alpha-particle radiotherapeutics using the Medical Internal Radiation Dose (MIRD) schema. |
| `find_alternative_drugs_ddinter` | Find alternative drugs that don't interact with contraindicated drugs using DDInter database for safer therapeutic substitutions. |
| `find_roi_from_image` | Find the ROIs (regions of interest) of protein bands from a Western blot or DNA electrophoresis image using threshold-based blob detection. Returns annotated image path and list of ROI coordinates. Use analyze_pixel_distribution first to determine appropriate threshold values. The returned ROI list can be converted to target_bands format for analyze_western_blot. |
| `get_fda_drug_label_info` | Retrieve FDA drug label information including indications, contraindications, warnings, and dosage information from the OpenFDA database. |
| `grade_adverse_events_using_vcog_ctcae` | Grade and monitor adverse events in animal studies using the VCOG-CTCAE standard. |
| `perform_mwas_cyp2c19_metabolizer_status` | Perform a Methylome-wide Association Study (MWAS) to identify CpG sites significantly associated with CYP2C19 metabolizer status. |
| `predict_admet_properties` | Predicts ADMET (Absorption, Distribution, Metabolism, Excretion, Toxicity) properties for a list of compounds using pretrained models. |
| `predict_binding_affinity_protein_1d_sequence` | Predicts binding affinity between small molecules and a protein sequence using pre-trained deep learning models. |
| `query_drug_interactions` | Query drug-drug interactions from DDInter database to identify potential interactions, mechanisms, and severity levels between specified drugs. |
| `query_fda_adverse_events` | Query FDA adverse event reports for specific drugs from the OpenFDA database to identify potential safety signals, reaction patterns, and regulatory intelligence. |
| `retrieve_topk_repurposing_drugs_from_disease_txgnn` | Computes TxGNN model predictions for drug repurposing and returns the top predicted drugs with their scores for a given disease. |
| `run_3d_chondrogenic_aggregate_assay` | Generates a detailed protocol for performing a 3D chondrogenic aggregate culture assay to evaluate compounds' effects on chondrogenesis. |
| `run_autosite` | Runs AutoSite on a PDB file to identify potential binding sites and returns a research log with the results. |
| `run_diffdock_with_smiles` | Run DiffDock molecular docking using a protein PDB file and a SMILES string for the ligand, executing the process in a Docker container. |

## physiology (11)

| Tool | Description |
|---|---|
| `analyze_abr_waveform_p1_metrics` | Extracts P1 amplitude and latency from Auditory Brainstem Response (ABR) waveform data. |
| `analyze_ciliary_beat_frequency` | Analyze ciliary beat frequency from high-speed video microscopy data using FFT analysis. |
| `analyze_endolysosomal_calcium_dynamics` | Analyze calcium dynamics in endo-lysosomal compartments using ELGA/ELGA1 probe data. |
| `analyze_fatty_acid_composition_by_gc` | Analyzes fatty acid composition in tissue samples using gas chromatography data. |
| `analyze_hemodynamic_data` | Analyzes raw blood pressure data to calculate key hemodynamic parameters. |
| `analyze_protein_colocalization` | Analyze colocalization between two fluorescently labeled proteins in microscopy images. |
| `calculate_brain_adc_map` | Calculate Apparent Diffusion Coefficient (ADC) map from diffusion-weighted MRI data using monoexponential diffusion model. |
| `perform_cosinor_analysis` | Performs cosinor analysis on physiological time series data to characterize circadian rhythms. |
| `quantify_amyloid_beta_plaques` | Analyzes an image to detect and quantify amyloid-beta plaques, returning a detailed analysis log. |
| `reconstruct_3d_face_from_mri` | Generate a 3D model of facial anatomy from MRI scans of the head and neck. |
| `simulate_thyroid_hormone_pharmacokinetics` | Simulates the transport and binding of thyroid hormones across different tissue compartments using an ODE-based pharmacokinetic model. |

## protocols (4)

| Tool | Description |
|---|---|
| `get_protocol_details` | Retrieve detailed metadata for a specific protocols.io protocol by ID. |
| `list_local_protocols` | List available protocol files in the local biomni/tool/protocols/ directory. Includes protocols from Addgene and Thermo Fisher Scientific. |
| `read_local_protocol` | Read the contents of a local protocol file from biomni/tool/protocols/. Use list_local_protocols() first to find available protocol filenames. |
| `search_protocols` | Search protocols.io for public protocols matching a keyword. |

## support_tools (4)

| Tool | Description |
|---|---|
| `download_data_lake_file` | Download a Biomni-Lite data lake file from Zenodo on demand. Files are cached locally — if already downloaded, this returns immediately. |
| `download_synapse_data` | Download data from Synapse using entity IDs. Requires SYNAPSE_AUTH_TOKEN environment variable for authentication. CRITICAL: Always specify entity_type parameter based on what you're downloading (file, dataset, folder, project). Check user hints like 'files' or search results to determine correct type. Multiple IDs only work with entity_type='file'. Recursive only works with entity_type='folder'. |
| `read_function_source_code` | Read the source code of a function from any module path. |
| `run_python_repl` | Executes the provided Python command in the notebook environment and returns the output. |

## synthetic_biology (8)

| Tool | Description |
|---|---|
| `analyze_bacterial_growth_rate` | Analyze bacterial growth data and extract growth parameters from OD600 measurements. |
| `analyze_barcode_sequencing_data` | Analyze sequencing data to extract, quantify and determine lineage relationships of barcodes. |
| `analyze_bifurcation_diagram` | Performs bifurcation analysis on a dynamical system and generates a bifurcation diagram. |
| `create_biochemical_network_sbml_model` | Generate a mathematical model of a biochemical network in SBML format. |
| `engineer_bacterial_genome_for_therapeutic_delivery` | Engineer a bacterial genome by integrating therapeutic genetic parts for therapeutic delivery. |
| `identify_fas_functional_domains` | Identifies functional domains within a Fatty Acid Synthase (FAS) sequence and predicts their roles. |
| `optimize_codons_for_heterologous_expression` | Analyzes and optimizes a DNA/RNA sequence for improved expression in a heterologous host organism. |
| `simulate_gene_circuit_with_growth_feedback` | Simulate gene regulatory circuit dynamics with growth feedback. |

## systems_biology (7)

| Tool | Description |
|---|---|
| `compare_protein_structures` | Compares two protein structures to identify structural differences and conformational changes. |
| `model_protein_dimerization_network` | Model protein dimerization networks to find equilibrium concentrations of dimers. |
| `perform_flux_balance_analysis` | Perform Flux Balance Analysis (FBA) on a genome-scale metabolic network model and return a research log of the process and results. |
| `query_chatnt` | Answer functions and properties questions for DNA sequences  |
| `simulate_metabolic_network_perturbation` | Construct and simulate kinetic models of metabolic networks and analyze their responses to perturbations. |
| `simulate_protein_signaling_network` | Simulate protein signaling network dynamics using ODE-based logic modeling with normalized Hill functions. |
| `simulate_renin_angiotensin_system_dynamics` | Simulate the time-dependent concentrations of renin-angiotensin system (RAS) components. |
