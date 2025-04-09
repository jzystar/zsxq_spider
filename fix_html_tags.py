import os
import re
import urllib.parse
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("fix_tags.log"), 
                              logging.StreamHandler()])
logger = logging.getLogger("fix_tags")

def clean_html_tags(text):
    """清理HTML标签，特别是处理<e>标签"""
    if not text:
        return text
        
    # 处理<e>标签，替换为title属性的URL解码内容
    def replace_e_tag(match):
        title = match.group(1)
        try:
            # URL解码
            decoded_title = urllib.parse.unquote(title)
            return decoded_title
        except Exception as e:
            logger.error(f"URL解码失败: {title}, 错误: {str(e)}")
            return title
    
    # 查找pattern: <e ... title="TITLE" ... />
    pattern = r'<e[^>]*?title="([^"]*)"[^>]*?/>'
    text = re.sub(pattern, replace_e_tag, text)
    
    return text

def process_markdown_files(directory='zsxq_posts'):
    """处理目录中的所有Markdown文件"""
    logger.info(f"开始处理目录: {directory}")
    
    # 获取目录中的所有md文件
    md_files = [f for f in os.listdir(directory) if f.endswith('.md')]
    logger.info(f"找到 {len(md_files)} 个Markdown文件")
    
    for filename in md_files:
        file_path = os.path.join(directory, filename)
        logger.info(f"处理文件: {file_path}")
        
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否包含HTML标签
            if '<e ' in content:
                logger.info(f"文件 {filename} 包含HTML标签，进行处理")
                new_content = clean_html_tags(content)
                
                # 写入新内容
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                logger.info(f"文件 {filename} 处理完成")
            else:
                logger.info(f"文件 {filename} 不包含HTML标签，跳过")
        except Exception as e:
            logger.error(f"处理文件 {filename} 时出错: {str(e)}")
            continue
    
    logger.info(f"所有文件处理完成")

if __name__ == "__main__":
    process_markdown_files() 