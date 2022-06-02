"This class is about the computing of DNA samples"

from itertools import count
from typing import Callable
from python_tools import my_parser, my_function_timer
from collections import Counter
from random import randrange
from functools import reduce
from wisp_lib import species_map, encode_kmer_4, write_xgboost_data, load_mapping, optimal_splitting, kmer_indexing
from os import listdir
from json import dump
from pathlib import Path
from constants import COUNT_METHOD


class Sample:

    @property
    def specie(self):
        return self.__specie

    @specie.setter
    def specie(self, new_specie):
        self.__specie = new_specie

    @property
    def seq(self):
        return self.__seq

    @seq.setter
    def seq(self, new_seq):
        self.__seq = new_seq

    @property
    def counts(self):
        return self.__counts

    @property
    def size(self):
        return self.__size

    @size.setter
    def size(self, sz):
        self.__size = sz

    @property
    def pattern(self):
        return self.__pattern

    @pattern.setter
    def pattern(self, pattern):
        self.__pattern = pattern

    @property
    def ksize(self):
        return self.__ksize

    @ksize.setter
    def ksize(self, ksz):
        self.__ksize = ksz

    @counts.setter
    def counts(self, kmer_counts):
        self.__counts = kmer_counts

    def post_creation_counting(self, count_func: Callable = COUNT_METHOD):
        self.counts = count_func(self.seq, self.ksize, self.pattern)

    def __init__(self, seq_dna: str, kmer_size: int, pattern: str, seq_specie: str | None = None, counting=True, count_func: Callable = COUNT_METHOD):
        """Inits a new Sample object, container for sequence

        Args:
            seq_dna (str): nucleotides in seq
            kmer_size (int): size of kmer we will sample in this seq
            seq_specie (str | None, optional): name of specie we're looking at. Defaults to None.
        """
        self.specie = seq_specie  # name of file
        self.seq = seq_dna  # nucleotides
        self.size = len(seq_dna)  # size of seq
        self.ksize = kmer_size
        self.pattern = pattern
        self.counts = count_func(
            seq_dna, kmer_size, pattern) if counting else Counter()  # allows to load a full genome without computing it

    def update_counts(self, func: Callable, ratio: float) -> None:
        """Filters out results which are not matching func threshold

        Args:
            func (Callable): a limitation function
            ratio (float): a ratio by whom we multiply func results
        """
        self.counts = Counter(
            {x: val for x, val in self.counts.items() if val > ratio*func(self.counts.values())})

    def encoding_mapping(self, num_sp: int):
        """
        Retun an entry for XGBoost formated according to LIBSVS system
        """
        return str(num_sp) + " " + ' '.join([f"{encode_kmer_4(k)}:{v}" for k, v in self.counts.items()])


def call_loader(path: str, size_kmer: int, classif_level_int: int, filter: str | None, type_data: str, pattern: str) -> list:
    """Calls concurentially genomes loading inside sample objects

    Args:
        path (str): path to targeted genomes
        size_kmer (int): length of sampling for kmers
        classif_level_int (int): level of classification we're working at : 0 -> domain, 1 -> phylum ...
        filter (str | None): previously determined taxa if exists
        type_data (str): 'unk', 'train' or 'test'

    Returns:
        list: a list of samples
    """
    if filter == None or type_data == 'unk':
        lst_sequences = [l for l in listdir(path)]
    else:
        lst_sequences = [l for l in listdir(
            path) if l.split('_')[classif_level_int-1] == filter]
    lst_sequences = [(f"{path}", f"{elt}", size_kmer) for elt in lst_sequences]
    return [load_and_compute_one_genome(path_file, elt, size_km, pattern) for (path_file, elt, size_km) in lst_sequences]
    #my_futures_collector(load_and_compute_one_genome, lst_sequences, 10)


def load_and_compute_one_genome(path: str, elt: str, size_kmer: int, pattern: str) -> Sample:
    """Generate sample for one genome

    Args:
        path (str): path to genome
        elt (str): name of genome to compute
        size_kmer (int): size of kmer sampling

    Returns:
        Sample: a sample which merges all sequences from the file
    """
    parsed = my_parser(f"{path}{elt}", clean=True, merge=True, merge_name=elt)
    return Sample(
        seq_dna=parsed[elt],
        kmer_size=size_kmer,
        seq_specie=elt.split('/')[-1],
        counting=False,
        pattern=pattern
    )


def generate_diversity(spl: Sample, sample_number: int, size_kmer: int, size_read: int) -> list[Sample]:
    if size_read > spl.size:
        # if we cant etablsih subread, we do it anyways
        size_read = int(spl.size/2)
    read: str = f"{spl.seq}{spl.seq[-(size_kmer-1):]}"
    spl_list: list = []
    for _ in range(sample_number):
        x = randrange(0, len(read)-size_read-size_kmer)
        subread = read[x:x+size_read+size_kmer]
        spl_list.append(
            Sample(subread, size_kmer, spl.specie))
    return spl_list


def overhaul_diversity(spl: Sample, sample_number: int, size_kmer: int, size_read: int) -> list[Sample]:
    try:
        return [Sample(spl.seq[x:x+size_read+len(spl.pattern)], size_kmer, spl.pattern, spl.specie) for x in [randrange(0, spl.size-size_read-size_kmer) for _ in range(sample_number)]]
    except:
        spl.post_creation_counting()
        return [spl]


def print_sample_list(spl: list[Sample]) -> None:
    for e in spl:
        print(f"{e} <|> {e.counts.most_common(3)}")


def sum_counter_list(spl: list[Sample]) -> Counter:
    """
    Outputs the sum for 1 given file of all subCounter
    """
    return reduce(lambda x, y: x+y, [e.counts for e in spl])


def mapping_sp(input_dir: str, path: str, classif_level: str, db_name: str, int_level: int, taxa: str | None) -> dict:
    """Calls for a map of species, saves it, and return map as a dict

    Args:
        input_dir (str): dir where references genomes are stored
        path (str): path for database, used to save the map
        classif_level (str): _description_
        db_name (str): _description_
        int_level (int): _description_
        taxa (str | None): _description_

    Returns:
        dict: a map of species for gien taxa
    """
    list_sp = species_map(input_dir, int_level, taxa)
    my_path = f"{path}{db_name}/{classif_level}/{taxa}_saved_mapping.json" if taxa != None else f"{path}{db_name}/{classif_level}/saved_mapping.json"
    with open(my_path, 'w') as file_manager:
        dump(list_sp, file_manager)
    return list_sp


def mapping_merged_sp(input_dir: str, path: str, db_name: str) -> dict:
    """Calls for a map of species, saves it, and return map as a dict

    Args:
        input_dir (str): dir where references genomes are stored
        path (str): path for database, used to save the map
        classif_level (str): _description_
        db_name (str): _description_
        int_level (int): _description_
        taxa (str | None): _description_

    Returns:
        dict: a map of species for given taxa
    """
    list_sp = species_map(input_dir, 4)
    my_path = f"{path}{db_name}/merged/merged_saved_mapping.json"
    with open(my_path, 'w') as file_manager:
        dump(list_sp, file_manager)
    return list_sp


@my_function_timer("Building datasets")
def make_datasets(input_style: bool | str, job_name: str, input_dir: str, path: str, datas: list[str], sampling: int, db_name: str, classif_level: str, kmer_size: int, read_size: int, pattern: str,  sp_determied: str | None):
    """
    Create the datasets and calls for storage

    * input_dir (str) : path to directory with reference genomes
    * path (str) : location where .txt.train, .txt.unk and .txt.test are stored
    * job_name (str) : name of job, identificator
    * classif_level (str) : level of cassification we're working at
    * db_name (str) : database we need to search in
    """
    # iteration levels
    taxa: dict = {'domain': 0, 'phylum': 1,
                  'group': 2, 'order': 3, 'family': 4}
    if datas == ['train', 'test']:
        # safe creation of dir
        Path(f"{path}{db_name}/{classif_level}/").mkdir(parents=True, exist_ok=True)
        # we re-generate database, so we need to map it out
        if classif_level != 'merged':
            sp_map = mapping_sp(f"{input_dir}train/", path,
                                classif_level, db_name, taxa[classif_level], sp_determied)
        else:
            sp_map = mapping_merged_sp(f"{input_dir}train/", path, db_name)
    else:
        # database already generated, loading mapping without erasing it
        sp_map = load_mapping(path, db_name,
                              classif_level, sp_determied)

    for type_data in datas:
        if isinstance(input_style, bool):
            if classif_level != 'merged':
                my_sp = list(call_loader(
                    f"{input_dir}train/", kmer_size, taxa[classif_level], sp_determied, type_data, pattern))
            else:
                my_sp = list(call_loader(
                    f"{input_dir}train/", kmer_size, 4, None, type_data, pattern))
        else:
            fileholder = my_parser(
                f"{input_dir}{type_data}/{input_style}", True, True, "unk_sample")
            my_sp = [Sample(fileholder['unk_sample'],
                            kmer_size, counting=False, pattern=pattern)]
        lines = []
        for sp in my_sp:
            # iterate through all samples and creates subsampling
            if type_data == 'test':
                my_ssp = overhaul_diversity(
                    sp, int(sampling/8), kmer_size, read_size)
            else:
                my_ssp = overhaul_diversity(sp, sampling, kmer_size, read_size)
            for s in my_ssp:
                if type_data == 'train' or type_data == 'test':
                    if classif_level != 'merged':
                        lines.append(s.encoding_mapping(
                            sp_map[s.specie.split('_')[taxa[classif_level]]]))
                    else:
                        lines.append(s.encoding_mapping(
                            sp_map[s.specie.split('_')[4]]))
                else:
                    lines.append(s.encoding_mapping(0))
        write_xgboost_data(lines, path,
                           classif_level, type_data, db_name, job_name, sp_determied)


@my_function_timer("Building datasets")
def make_unk_datasets(input_sequence: str, job_name: str, input_dir: str, path: str, datas: list[str], sampling: int, db_name: str, classif_level: str, kmer_size: int, read_size: int, pattern: str,  sp_determied: str | None):
    """
    Create the datasets and calls for storage

    * input_dir (str) : path to directory with reference genomes
    * path (str) : location where .txt.train, .txt.unk and .txt.test are stored
    * job_name (str) : name of job, identificator
    * classif_level (str) : level of cassification we're working at
    * db_name (str) : database we need to search in
    """
    # TODO testing
    all_reads = optimal_splitting(input_sequence, read_size, sampling)
    all_counts = [kmer_indexing(read, kmer_size, pattern)
                  for read in all_reads]
    lines = [
        f"0 {' '.join([str(encode_kmer_4(k))+':'+str(v) for k, v in counts])}" for counts in all_counts]
    write_xgboost_data(lines, path,
                       classif_level, 'unk', db_name, job_name, sp_determied)
