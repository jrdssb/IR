import catch_url
import es_createInex

# 文件路径
txt_file = 'urls_with_data.txt'



def main():
    catch_url.cu()
    es_createInex.index_data_to_elasticsearch(txt_file)
