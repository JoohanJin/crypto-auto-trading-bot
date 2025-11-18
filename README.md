<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<!-- <a name="readme-top"></a> -->
<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
<!-- [![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url] -->



<!-- PROJECT LOGO -->
<br />
<div align="center">


<h2 align="center">Crypto-Currency Automatic Trading Bot</h3>

  <p align="center">
    <!-- project_description -->
    <!-- <br /> -->
    <!-- <a href="https://github.com/JoohanJin/AutoCryptoTrading"><strong>Explore the docs »</strong></a> -->
    <!-- <br /> -->
    <!-- <br /> -->
    <!-- <a href="https://github.com/JoohanJin/AutoCryptoTrading">View Demo</a> -->
    <!-- · -->
    <!-- <a href="https://github.com/JoohanJin/AutoCryptoTrading/issues">Report Bug</a> -->
    <!-- · -->
    <!-- <a href="https://github.com/JoohanJin/AutoCryptoTrading/issues">Request Feature</a> -->
  </p>
</div>

A personal crypto trading bot project built to automate trading strategies using real-time data from the MEXC Exchange. More brokers can be added in the future for more accurate and reiliable data fetching.


<!-- TABLE OF CONTENTS -->
<!-- <details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details> -->



<!-- ABOUT THE PROJECT -->
## 📌 About The Project

<!-- [![Product Name Screen Shot][product-screenshot]](https://example.com) -->

This bot connects to the MEXC Broker via WebSocket, processes market data, and is desinged to execute trades based on predefined strategies. Currently under development, with order placement and strategy refinedment in progress.

It is not a high-frequency trading system; rather, it is a simple tool that will execute orders based on a trading strategy I have been used.
Potentially, a high frequency trading can be developed in the future based on the needs.

Recently deployed v1_0 on my home server.

---

## 🛠️ Features
- Real-time market data fetching via websocket api.
- Strategy logic for automated decision-making.
- Future support for order placement.
- Modular design for testing and expansion.
- Order placement is enabled on Binance Broker.

<!-- <p align="right">(<a href="#readme-top">back to top</a>)</p> -->
---

## Milestone
- Please refer to [Here](https://github.com/JoohanJin/AutoCryptoTrading/tree/dev/Docs/TODO)

---

## Architecture Diagram

![Architecture Diagram](https://raw.githubusercontent.com/JoohanJin/AutoCryptoTrading/stable/Media/AutoTradingBot%20DIagram.png)

---

## 🧰 Tech Stack

* **Lanauge**: [![Python3][Python3-img]][Python3-url]
* **Exchange**: MEXC, Binance
* **libraires**:
  * [![Pandas][Pandas-img]][Pandas-url]
  * [![NumPy][Numpy-img]][Numpy-url]
* **Tools**:
  * [![Jupyter Notebook][Jupyter-img]][Jupyter-url]
  * Github Actions (CI)
  * Docker

<!-- <p align="right">(<a href="#readme-top">back to top</a>)</p> -->

--- 

## Branch Structure

```text
stable
└── dev
    ├── dev-feature1
    ├── dev-feature2
    └── dev-feature3
```

---

## 🚀 Procedure

### Prerequisites

Before getting started, ensure you have:
- **Python 3.10+** (or Docker as an alternative)
- **MEXC API Credentials** - [MexC Exchange](https://www.mexc.com/)
- **Binance API Credentials** - [Binance Exchange](https://www.binance.com/en)
- **Telegram Bot Token & Chat ID** - For trade notifications
- **Docker** (optional, but recommended for deployment)

### Getting Started

#### Option 1: Local Setup

1. **Clone the repository**
    ```sh
    git clone https://github.com/JoohanJin/AutoCryptoTrading.git
    cd AutoCryptoTrading
    ```

2. **Create and configure `.env` file**
    - Copy `.env_template` to `.env`
    - Fill in your API credentials and Telegram details
    ```sh
    cp .env_template .env
    ```

3. **Set up Python environment**
    ```sh
    python3.10 -m venv <venv_dir_name>
    source <venv_dir_name>/bin/activate
    pip install -r requirements.txt
    ```

4. **Run the bot**
    ```sh
    python src/main.py
    ```

#### Option 2: Docker Deployment (Recommended for 24/7)

1. **Clone the repository**
    ```sh
    git clone https://github.com/JoohanJin/AutoCryptoTrading.git
    cd AutoCryptoTrading
    ```

2. **Configure `.env` file**
    ```sh
    cp .env_template .env
    # Edit .env with your credentials
    nano .env
    ```

3. **Build the Docker image**
    ```sh
    docker buildx build --platform linux/amd64 -t autocrypto-trading:latest .
    ```
    > Replace `linux/amd64` with your desired architecture (e.g., `linux/arm64` for ARM)

4. **Run the container**
    ```sh
    docker run -d \
      --name crypto-trading-bot \
      --env-file .env \
      --restart unless-stopped \
      autocrypto-trading:latest
    ```

5. **Monitor the bot**
    ```sh
    docker logs -f crypto-trading-bot
    ```

### Configuration Notes

- **Telegram**: Required for trade notifications (can be optional in future versions)
- **API Keys**: Ensure you use keys with appropriate permissions (trading enabled, IP whitelisting recommended)
- **For Production**: Use environment variables instead of storing credentials in `.env` files

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/github_username/repo_name.svg?style=for-the-badge
[contributors-url]: https://github.com/JoohanJin/AutoCryptoTrading/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/github_username/repo_name.svg?style=for-the-badge
[forks-url]: https://github.com/JoohanJin/AutoCryptoTrading/network/members
[stars-shield]: https://img.shields.io/github/stars/github_username/repo_name.svg?style=for-the-badge
[stars-url]: https://github.com/JoohanJin/AutoCryptoTrading/stargazers
[issues-shield]: https://img.shields.io/github/issues/github_username/repo_name.svg?style=for-the-badge
[issues-url]: https://github.com/JoohanJin/AutoCryptoTrading/issues
[license-shield]: https://img.shields.io/github/license/github_username/repo_name.svg?style=for-the-badge
[license-url]: https://github.com/JoohanJin/AutoCryptoTrading/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/linkedin_username
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com 
[Python3-img]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[Python3-url]: https://www.python.org/
[Jupyter-img]: https://img.shields.io/badge/jupyter-%23FA0F00.svg?style=for-the-badge&logo=jupyter&logoColor=white
[Jupyter-url]: https://jupyter.org/
[Numpy-img]: https://img.shields.io/badge/numpy-%23013243.svg?style=for-the-badge&logo=numpy&logoColor=white
[Numpy-url]: https://numpy.org/
[Pandas-img]: https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white
[Pandas-url]: https://pandas.pydata.org/
