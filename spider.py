import requests
import json
import os
import time
import base64
import urllib.parse
import logging
import re
import datetime
from config import zsxq_access_token, group_id, user_agent

# 设置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("zsxq_spider.log"), 
                              logging.StreamHandler()])
logger = logging.getLogger("zsxq_spider")

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
        except:
            return title
    
    # 查找pattern: <e ... title="TITLE" ... />
    pattern = r'<e[^>]*?title="([^"]*)"[^>]*?/>'
    text = re.sub(pattern, replace_e_tag, text)
    
    return text

def download_file(url, folder, filename):
    """下载文件并保存到指定文件夹"""
    os.makedirs(folder, exist_ok=True)
    
    try:
        headers = {
            'User-Agent': user_agent,
            'Cookie': f'zsxq_access_token={zsxq_access_token}',
            'Referer': f'https://wx.zsxq.com/group/{group_id}'
        }
        
        logger.info(f"正在下载: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            file_path = os.path.join(folder, filename)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"成功下载: {file_path}")
            return file_path
        else:
            logger.error(f"下载失败: {url}, 状态码: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"下载出错: {url}, 错误: {str(e)}")
        return None

def convert_time(time_str):
    """转换时间格式"""
    try:
        dt = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S%z")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"时间格式转换失败: {time_str}, 错误: {str(e)}")
            return time_str

def get_filename_time(time_str):
    """获取用于文件名的时间格式"""
    try:
        dt = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        return dt.strftime("%Y-%m-%d_%H-%M-%S")
    except ValueError:
        try:
            dt = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S%z")
            return dt.strftime("%Y-%m-%d_%H-%M-%S")
        except Exception as e:
            logger.error(f"时间格式转换失败: {time_str}, 错误: {str(e)}")
            return time.strftime("%Y-%m-%d_%H-%M-%S")  # 使用当前时间作为备选

def sanitize_filename(filename):
    """清理文件名，移除不合法字符"""
    # 移除不允许在文件名中使用的字符
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def get_topics(count=20, end_time=None, max_retries=5, retry_delay=3):
    """获取知识星球的帖子"""
    url = f"https://api.zsxq.com/v2/groups/{group_id}/topics"
    
    headers = {
        'User-Agent': user_agent,
        'Cookie': f'zsxq_access_token={zsxq_access_token}',
        'Content-Type': 'application/json',
        'Referer': f'https://wx.zsxq.com/group/{group_id}'
    }
    
    params = {
        'scope': 'all',
        'count': count
    }
    
    # 如果提供了end_time参数，添加到请求中
    if end_time:
        params['end_time'] = end_time
    
    # 创建响应保存目录
    response_dir = 'response'
    os.makedirs(response_dir, exist_ok=True)
    
    retries = 0
    while retries <= max_retries:
        try:
            if retries > 0:
                logger.info(f"第 {retries} 次重试获取帖子，数量: {count}, 结束时间: {end_time if end_time else '无'}")
            else:
                logger.info(f"正在获取知识星球帖子，数量: {count}, 结束时间: {end_time if end_time else '无'}")
                
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"成功获取帖子数据，状态: {response.status_code}")
                
                # 将原始API响应保存到response目录中
                response_file = os.path.join(response_dir, f"zsxq_api_response_{time.strftime('%Y%m%d%H%M%S')}.json")
                try:
                    with open(response_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    logger.info(f"API响应已保存至: {response_file}")
                except Exception as e:
                    logger.error(f"保存API响应时出错: {e}")
                
                # 检查响应数据结构
                if 'resp_data' not in data:
                    logger.error(f"API响应中缺少 resp_data 字段: {data.keys()}")
                    if 'code' in data and 'msg' in data:
                        logger.error(f"API错误: 代码 {data['code']}, 消息: {data['msg']}")
                    # 如果达到最大重试次数，返回None
                    if retries >= max_retries:
                        logger.error(f"达到最大重试次数 {max_retries}，获取帖子失败")
                        return None
                    # 否则重试
                    retries += 1
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue
                
                if 'topics' not in data['resp_data'] or not data['resp_data']['topics']:
                    logger.error(f"API响应中的 resp_data 缺少 topics 字段或为空: {data['resp_data'].keys()}")
                    # 如果达到最大重试次数，返回None
                    if retries >= max_retries:
                        logger.error(f"达到最大重试次数 {max_retries}，获取帖子失败")
                        return None
                    # 否则重试
                    retries += 1
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue
                
                topics = data['resp_data']['topics']
                logger.info(f"成功解析API响应，获取到 {len(topics)} 个帖子")
                return topics
            else:
                logger.error(f"获取帖子数据失败: {response.status_code}")
                logger.error(response.text)
                # 如果达到最大重试次数，返回None
                if retries >= max_retries:
                    logger.error(f"达到最大重试次数 {max_retries}，获取帖子失败")
                    return None
                # 否则重试
                retries += 1
                logger.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"获取帖子时发生错误: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # 如果达到最大重试次数，返回None
            if retries >= max_retries:
                logger.error(f"达到最大重试次数 {max_retries}，获取帖子失败")
                return None
            # 否则重试
            retries += 1
            logger.info(f"等待 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)
    
    # 如果所有重试都失败，返回None
    return None

def get_topics_in_batches(total_count=200, batch_size=20, delay=2, start_time=None):
    """分批次获取指定数量的帖子
    
    参数:
        total_count (int): 要获取的帖子总数量
        batch_size (int): 每批次获取的帖子数量
        delay (int): 批次之间的等待时间(秒)
        start_time (str): 开始时间，格式为 "YYYY-MM-DDTHH:MM:SSZ" 或 "YYYY-MM-DD"，只获取晚于此时间的帖子
    """
    all_topics = []
    batches_needed = total_count // batch_size
    end_time = None  # 初始不设置结束时间，获取最新的帖子
    # 记录连续获取帖子数量少于batch_size的次数
    consecutive_small_batches = 0
    
    # 处理start_time，转换为datetime对象用于比较
    start_datetime = None
    if start_time:
        try:
            # 尝试解析多种可能的日期格式
            if 'T' in start_time:
                if start_time.endswith('Z'):
                    start_datetime = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
                    start_datetime = start_datetime.replace(tzinfo=datetime.timezone.utc)
                elif '+' in start_time:
                    start_datetime = datetime.datetime.fromisoformat(start_time)
                else:
                    start_datetime = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
                    start_datetime = start_datetime.replace(tzinfo=datetime.timezone.utc)
            else:
                # 如果只提供日期，设置为当天的0点
                start_datetime = datetime.datetime.strptime(start_time, "%Y-%m-%d")
                start_datetime = start_datetime.replace(tzinfo=datetime.timezone.utc)
            
            logger.info(f"将只获取晚于 {start_datetime} 的帖子")
        except ValueError as e:
            logger.error(f"开始时间格式错误: {start_time}, 错误: {str(e)}")
            logger.info("将获取所有帖子")
    
    logger.info(f"开始分批获取帖子，总数: {total_count}，批次大小: {batch_size}，总批次: {batches_needed}")
    
    for batch in range(batches_needed):
        # 获取一批帖子
        topics = get_topics(count=batch_size, end_time=end_time)
        
        if not topics or len(topics) == 0:
            logger.warning(f"批次 {batch+1} 未获取到任何帖子，结束抓取")
            break
        
        current_batch_size = len(topics)
        logger.info(f"批次 {batch+1}/{batches_needed} 成功获取 {current_batch_size} 个帖子")
        
        # 检查是否连续3次获取的帖子数量少于batch_size
        if current_batch_size < batch_size:
            consecutive_small_batches += 1
            logger.info(f"当前批次帖子数量少于批次大小，连续小批次计数: {consecutive_small_batches}/3")
            if consecutive_small_batches >= 3:
                logger.info(f"连续 {consecutive_small_batches} 次获取的帖子数量少于批次大小，停止抓取")
                break
        else:
            # 如果当前批次帖子数量等于batch_size，重置计数器
            consecutive_small_batches = 0
        
        # 如果设置了开始时间，过滤掉早于开始时间的帖子
        if start_datetime:
            filtered_topics = []
            all_too_old = True
            
            for topic in topics:
                create_time_raw = topic.get('create_time', '')
                try:
                    # 解析帖子创建时间
                    if '.' in create_time_raw:
                        topic_datetime = datetime.datetime.strptime(create_time_raw, "%Y-%m-%dT%H:%M:%S.%f%z")
                    else:
                        topic_datetime = datetime.datetime.strptime(create_time_raw, "%Y-%m-%dT%H:%M:%S%z")
                    
                    # 只收集晚于开始时间的帖子
                    if topic_datetime > start_datetime:
                        filtered_topics.append(topic)
                        all_too_old = False
                except Exception as e:
                    logger.error(f"解析时间错误: {create_time_raw}, 错误: {str(e)}")
                    # 如果无法解析时间，为安全起见包含该帖子
                    filtered_topics.append(topic)
                    all_too_old = False
            
            # 如果所有帖子都早于开始时间，停止抓取
            if all_too_old:
                logger.info("所有帖子都早于开始时间，停止抓取")
                break
            
            logger.info(f"过滤后保留 {len(filtered_topics)}/{len(topics)} 个晚于 {start_datetime} 的帖子")
            all_topics.extend(filtered_topics)
        else:
            # 没有开始时间限制，保留所有帖子
            all_topics.extend(topics)
        
        # 更新end_time为当前批次最后一个帖子的创建时间
        last_topic = topics[-1]
        end_time = last_topic.get('create_time')
        
        # 如果不是最后一批，则等待指定的延迟时间
        if batch < batches_needed - 1:
            logger.info(f"等待 {delay} 秒后获取下一批次...")
            time.sleep(delay)
            
    logger.info(f"共获取 {len(all_topics)} 个帖子")
    return all_topics

def get_comments(topic_id):
    """获取指定帖子的评论"""
    url = f"https://api.zsxq.com/v2/topics/{topic_id}/comments"
    
    headers = {
        'User-Agent': user_agent,
        'Cookie': f'zsxq_access_token={zsxq_access_token}',
        'Content-Type': 'application/json',
        'Referer': f'https://wx.zsxq.com/dweb2/index/topic/{topic_id}'
    }
    
    params = {
        'count': 100,  # 获取评论的数量
        'sort': 'asc'  # 按时间升序排序
    }
    
    # 创建响应保存目录
    response_dir = 'response'
    os.makedirs(response_dir, exist_ok=True)
    
    try:
        logger.info(f"正在获取帖子 {topic_id} 的评论")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"成功获取评论数据，状态: {response.status_code}")
            
            # 检查响应数据结构
            if 'resp_data' not in data:
                logger.error(f"API响应中缺少 resp_data 字段: {data.keys()}")
                return []
            
            if 'comments' not in data['resp_data']:
                logger.info(f"帖子 {topic_id} 没有评论")
                return []
            
            comments = data['resp_data']['comments']
            logger.info(f"成功获取到 {len(comments)} 条评论")
            
            # 将原始API响应保存到response目录中
            response_file = os.path.join(response_dir, f"zsxq_comments_{topic_id}_{time.strftime('%Y%m%d%H%M%S')}.json")
            try:
                with open(response_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"评论响应已保存至: {response_file}")
            except Exception as e:
                logger.error(f"保存评论响应时出错: {e}")
            
            return comments
        else:
            logger.error(f"获取评论失败，状态码: {response.status_code}, 响应: {response.text}")
            return []
    except Exception as e:
        logger.error(f"获取评论时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def create_markdown_for_topic(topic, output_dir, images_dir, files_dir):
    """为单个帖子创建Markdown文件"""
    try:
        # 帖子基本信息
        topic_type = topic.get('type', '')
        topic_id = topic.get('topic_id', '')
        create_time_raw = topic.get('create_time', '')
        create_time = convert_time(create_time_raw)
        file_time = get_filename_time(create_time_raw)
        
        # 作者信息
        talk = None
        if 'talk' in topic:
            talk = topic['talk']
        elif 'question' in topic:
            talk = topic['question']
        
        if not talk:
            logger.warning(f"帖子 {topic_id} 没有内容")
            return
        
        author = talk.get('owner', {})
        author_name = author.get('name', '未知作者')
        safe_author_name = sanitize_filename(author_name)
        
        # 创建文件名
        filename = f"{file_time}_{safe_author_name}.md"
        file_path = os.path.join(output_dir, filename)
        
        # 如果文件已存在，跳过处理
        if os.path.exists(file_path):
            logger.info(f"帖子文件已存在，跳过: {file_path}")
            return file_path
        
        # 帖子内容
        content = ''
        if 'text' in talk:
            content = talk['text']
            # 清理HTML标签
            content = clean_html_tags(content)
        
        logger.info(f"正在处理帖子: {topic_id}, 保存到: {filename}")
        
        # 创建Markdown文件
        with open(file_path, 'w', encoding='utf-8') as md_file:
            # 写入帖子标题
            md_file.write(f"# {author_name} 发表于 {create_time}\n\n")
            md_file.write(f"帖子ID: {topic_id}\n\n")
            
            # 写入帖子内容
            md_file.write(f"{content}\n\n")
            
            # 处理图片
            if 'images' in talk and talk['images']:
                md_file.write("## 图片\n\n")
                for img_idx, img in enumerate(talk['images']):
                    if 'original' in img and 'url' in img['original']:
                        img_url = img['original']['url']
                        img_name = f"topic_{topic_id}_image_{img_idx+1}.jpg"
                        local_path = download_file(img_url, images_dir, img_name)
                        if local_path:
                            rel_path = os.path.join('images', img_name).replace('\\', '/')
                            md_file.write(f"![图片 {img_idx+1}]({rel_path})\n\n")
                    elif 'url' in img:
                        img_url = img['url']
                        img_name = f"topic_{topic_id}_image_{img_idx+1}.jpg"
                        local_path = download_file(img_url, images_dir, img_name)
                        if local_path:
                            rel_path = os.path.join('images', img_name).replace('\\', '/')
                            md_file.write(f"![图片 {img_idx+1}]({rel_path})\n\n")
            
            # 处理文件（PDF等）
            if 'files' in talk and talk['files']:
                md_file.write("## 文件\n\n")
                for file_idx, file in enumerate(talk['files']):
                    if 'name' in file:
                        file_name = file['name']
                    
                        md_file.write(f"文件 {file_idx+1}: {file_name}\n\n")

            
            # 获取并处理评论
            comments = get_comments(topic_id)
            
            # 如果API不返回评论，尝试从帖子本身的show_comments字段获取
            if len(comments) == 0 and 'show_comments' in topic:
                comments = topic['show_comments']
                
            if len(comments) > 0:
                md_file.write("## 评论\n\n")
                
                for comment in comments:
                    comment_id = comment.get('comment_id', '')
                    comment_time = convert_time(comment.get('create_time', ''))
                    comment_owner = comment.get('owner', {})
                    comment_author = comment_owner.get('name', '未知用户')
                    comment_text = clean_html_tags(comment.get('text', ''))
                    likes_count = comment.get('likes_count', 0)
                    
                    # 处理回复的评论
                    if 'parent_comment_id' in comment and 'repliee' in comment:
                        repliee = comment.get('repliee', {})
                        repliee_name = repliee.get('name', '未知用户')
                        md_file.write(f"**{comment_author}** 回复 **{repliee_name}** ({comment_time}):\n\n{comment_text}\n\n")
                    else:
                        md_file.write(f"**{comment_author}** ({comment_time}):\n\n{comment_text}\n\n")
                    
                    # 处理评论中的图片
                    if 'images' in comment and comment['images']:
                        for img_idx, img in enumerate(comment['images']):
                            if 'large' in img and 'url' in img['large']:
                                img_url = img['large']['url']
                                img_name = f"comment_{comment_id}_image_{img_idx+1}.jpg"
                                local_path = download_file(img_url, images_dir, img_name)
                                if local_path:
                                    rel_path = os.path.join('images', img_name).replace('\\', '/')
                                    md_file.write(f"![评论图片 {img_idx+1}]({rel_path})\n\n")
                    
                    # 添加分隔线
                    md_file.write("---\n\n")
        
        logger.info(f"成功保存帖子: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"处理帖子时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def create_markdown(topics):
    """将帖子数据转换为Markdown格式，每个帖子一个文件"""
    if not topics:
        logger.error("没有获取到数据")
        return
    
    if len(topics) == 0:
        logger.error("没有获取到任何帖子")
        return
        
    logger.info(f"开始处理 {len(topics)} 个帖子")
    
    # 创建输出文件夹
    output_dir = 'zsxq_posts'
    images_dir = os.path.join(output_dir, 'images')
    files_dir = os.path.join(output_dir, 'files')
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(files_dir, exist_ok=True)
    
    # 创建索引文件
    index_path = os.path.join(output_dir, 'index.md')
    
    # 如果索引文件存在，读取现有内容
    existing_entries = set()  # 已处理的文件名集合
    existing_entries_data = []  # 已有的索引条目数据
    
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as existing_index:
            lines = existing_index.readlines()
            # 提取已存在的帖子信息
            table_started = False
            
            for line in lines:
                # 跳过表头
                if '| 发布时间 |' in line:
                    table_started = True
                    continue
                if '|---------|' in line:
                    continue
                
                # 解析表格行
                if table_started and '|' in line and '.md' in line:
                    try:
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 5:  # 至少应有5部分（包括首尾的空字符串）
                            create_time = parts[1]
                            author_name = parts[2]
                            topic_id = parts[3]
                            filename_part = parts[4]
                            
                            # 提取文件名
                            filename = filename_part.split('(')[1].split(')')[0]
                            existing_entries.add(filename)
                            
                            # 保存完整条目数据
                            existing_entries_data.append((create_time, author_name, topic_id, filename))
                    except Exception as e:
                        logger.error(f"解析索引文件行时出错: {e}, 行: {line}")
            
    # 处理所有帖子
    new_entries = []
    
    for idx, topic in enumerate(topics):
        try:
            # 获取基本信息用于索引
            topic_id = topic.get('topic_id', '')
            create_time_raw = topic.get('create_time', '')
            create_time = convert_time(create_time_raw)
            
            talk = None
            if 'talk' in topic:
                talk = topic['talk']
            elif 'question' in topic:
                talk = topic['question']
            
            if not talk:
                logger.warning(f"帖子 #{idx+1} (ID: {topic_id}) 没有内容")
                continue
            
            author = talk.get('owner', {})
            author_name = author.get('name', '未知作者')
            safe_author_name = sanitize_filename(author_name)
            
            file_time = get_filename_time(create_time_raw)
            filename = f"{file_time}_{safe_author_name}.md"
            
            # 检查是否已处理过该文件
            if filename in existing_entries:
                logger.info(f"帖子已存在于索引中，跳过: {filename}")
                continue
            
            # 处理单个帖子的Markdown文件
            file_path = create_markdown_for_topic(topic, output_dir, images_dir, files_dir)
            
            if file_path:
                # 添加到新条目列表
                new_entries.append((create_time, author_name, topic_id, filename))
                logger.info(f"成功添加新帖子到索引: {filename}")
        except Exception as e:
            logger.error(f"处理索引时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    # 合并现有条目和新条目
    all_entries = existing_entries_data + new_entries
    
    # 检查是否有新内容添加
    if not new_entries:
        logger.info("没有新的帖子添加到索引中")
        return
    
    # 按时间排序所有条目（新的在前）
    all_entries.sort(reverse=True, key=lambda x: x[0])
    
    # 写入索引文件
    with open(index_path, 'w', encoding='utf-8') as index_file:
        index_file.write(f"# 知识星球帖子索引 - {group_id}\n\n")
        index_file.write("| 发布时间 | 作者 | 帖子ID | 文件链接 |\n")
        index_file.write("|---------|------|--------|----------|\n")
        
        # 写入排序后的所有条目
        for entry in all_entries:
            create_time, author_name, topic_id, filename = entry
            index_file.write(f"| {create_time} | {author_name} | {topic_id} | [{filename}]({filename}) |\n")
    
    logger.info(f"已成功更新帖子索引: {index_path}，添加了 {len(new_entries)} 个新帖子")

def save_run_time():
    """保存本次运行的时间到文件中，格式为ISO 8601"""
    current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        with open("lastrun.txt", "w", encoding="utf-8") as f:
            f.write(current_time)
        logger.info(f"已保存本次运行时间: {current_time}")
        return current_time
    except Exception as e:
        logger.error(f"保存运行时间失败: {e}")
        return None

def load_run_time():
    """从文件中加载上次运行的时间"""
    try:
        if os.path.exists("lastrun.txt"):
            with open("lastrun.txt", "r", encoding="utf-8") as f:
                last_run_time = f.read().strip()
            logger.info(f"读取到上次运行时间: {last_run_time}")
            return last_run_time
        else:
            logger.info("没有找到上次运行时间记录")
            return None
    except Exception as e:
        logger.error(f"读取上次运行时间失败: {e}")
        return None

def main():
    logger.info("开始抓取知识星球帖子...")
    
    # 获取命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='抓取知识星球帖子')
    
    # 读取上次运行时间作为默认开始时间
    last_run_time = load_run_time()
    
    # 添加命令行参数
    parser.add_argument('--start_time', type=str, default=last_run_time, 
                        help='开始时间，格式为YYYY-MM-DDTHH:MM:SSZ或YYYY-MM-DD，只获取晚于此时间的帖子。默认使用上次运行时间。')
    parser.add_argument('--total', type=int, default=200, help='要获取的帖子总数量')
    parser.add_argument('--batch_size', type=int, default=20, help='每批次获取的帖子数量')
    parser.add_argument('--delay', type=int, default=2, help='批次之间的等待时间(秒)')
    parser.add_argument('--ignore_last_run', action='store_true', help='忽略上次运行时间，获取所有帖子')
    args = parser.parse_args()
    
    # 如果指定忽略上次运行时间，则将开始时间设为None
    if args.ignore_last_run:
        args.start_time = None
        logger.info("已忽略上次运行时间，将获取所有帖子")
    
    # 保存本次运行时间
    run_time = save_run_time()
    
    # 分批次获取帖子
    all_topics = get_topics_in_batches(
        total_count=args.total,
        batch_size=args.batch_size,
        delay=args.delay,
        start_time=args.start_time
    )
    
    if all_topics:
        create_markdown(all_topics)
        logger.info(f"处理完成，下次运行可使用 --start_time={run_time} 参数只获取新帖子")
    else:
        logger.error("获取数据失败")
        
    logger.info(f"本次抓取完成，运行时间已保存: {run_time}")
    logger.info(f"如需获取新帖子，运行时可使用 --start_time={run_time}")
    
if __name__ == "__main__":
    main() 