"Creates the sample dataset to be predicted afterwards"
from time import time
from itertools import product
from typing import Generator
from pathlib import Path
from os import path
from json import load
from collections import Counter
from Bio import SeqIO
from tharospytools import revcomp


def validate_parameters(params: dict) -> bool:
    "Lists all conditions where a set of parameters is valid, and accepts the creation if so"
    return all(
        [
            # verifies that the pattern length respects ksize
            sum(params['pattern']) == params['ksize'],
        ]
    )


def encoder(ksize: int) -> dict:
    """Generates a dict of codes for kmers

    Args:
        ksize (int): length of kmer

    Returns:
        dict: kmer:code
    """
    return {code: encode_kmer(code) for code in map(''.join, product('ATCG', repeat=ksize))}


def encode_kmer(kmer: str) -> int:
    """Encodes a kmer into base 4 format

    Args:
        kmer (str): a k-sized word composed of A,T,C,G

    Returns:
        int: Encoding of kmer
    """
    mapper: dict = {
        'A': "0",
        'T': "3",
        'C': "1",
        'G': "2"
    }
    return int(''.join([mapper[k] for k in kmer]))


def build_sample(params_file: str, input_data: list[str]) -> str:
    "Builds a json file with taxa levels as dict information"
    # Loading params file
    with open(params_file, 'r', encoding='utf-8') as pfile:
        params: dict = load(pfile)

    # Guard to check if params are acceptable
    if not validate_parameters(params):
        raise RuntimeError("Incorrect parameter file")

    # creating encoder
    my_encoder: dict = encoder(ksize=params['ksize'])

    # Writing the database
    Path(f"{path.dirname(__file__)}/databases/").mkdir(parents=True, exist_ok=True)
    with open(output_path := f"{path.dirname(__file__)}/databases/unk_sample_{str(time()).replace('.','_')}.txt", 'w', encoding='utf-8') as jdb:

        # iterating over input genomes
        for genome in input_data:
            with open(genome, 'r', encoding='utf-8') as freader:
                genome_data: dict = {fasta.id: str(fasta.seq)
                                     for fasta in SeqIO.parse(freader, 'fasta')}
            for id_sequence, dna_sequence in genome_data.items():
                # Splitting of reads
                if len(dna_sequence) >= params['read_size']:
                    all_reads = splitting(
                        dna_sequence,
                        params['read_size'],
                        params['sampling']
                    )
                    # Counting kmers inside each read
                    counters: list[Counter] = [
                        counter(
                            read,
                            params['ksize'],
                            params['pattern']
                        ) for read in all_reads
                    ]
                    del all_reads

                    # Encoding reads for XGBoost
                    encoded: list = [{my_encoder[k]:v for k, v in cts.items()}
                                     for cts in counters]
                    del counters

                    for sample in encoded:
                        # Each read is a dict with code:count for kmer
                        jdb.write(
                            f"0 {' '.join([str(k)+':'+str(v) for k,v in sample.items()])} #{id_sequence}\n")

                    del encoded

    return output_path


def splitting(seq: str, window_size: int, max_sampling: int) -> Generator:
    """Splits a lecture into subreads

    Args:
        seq (str): a DNA sequence
        window_size (int): size of splits
        max_sampling (int): maximum number of samples inside lecture

    Raises:
        ValueError: if read is too short

    Yields:
        Generator: subreads collection
    """
    if len(seq) < window_size:
        raise ValueError("Read is too short.")
    shift: int = int((len(seq)-window_size)/max_sampling)
    for i in range(max_sampling):
        yield seq[shift*i:shift*i+window_size]


def pattern_filter(substring: str, pattern: list[int]) -> str:
    """Applies a positional filter over a string

    Args:
        substring (str): substring to clean
        pattern (list): integers to be multiplied by

    Returns:
        str: a cleaned kmer
    """
    return ''.join([char * pattern[i] for i, char in enumerate(substring)])


def counter(entry: str, kmer_size: int, pattern: list[int]) -> Counter:
    """Counts all kmers and filter non-needed ones

    Args:
        entry (str): a subread
        kmer_size (int): k size
        pattern (list[int]): 110110... pattern, to select specific chars in kmer

    Returns:
        Counter: counts of kmers inside subread
    """

    all_kmers: Generator = (entry[i:i+len(pattern)]
                            for i in range(len(entry)-len(pattern)-1))
    counts: Counter = Counter(all_kmers)
    rev_counts: Counter = Counter({revcomp(k): v for k, v in counts.items()})
    counts += rev_counts
    del rev_counts
    if not all(pattern):
        # All positions in pattern should not be kept, we apply filter
        counts = Counter({pattern_filter(k, pattern)
                         : v for k, v in counts.items()})
    for filtered_kmer in (alpha * kmer_size for alpha in ['A', 'T', 'C', 'G']):
        del counts[filtered_kmer]
    return counts